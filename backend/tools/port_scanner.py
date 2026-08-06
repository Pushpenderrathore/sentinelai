"""
Port scanner with CVE/CWE risk mapping.
Scans common ports in parallel, grabs banners, and maps each open
service to known vulnerabilities — similar to Shodan's basic view.
"""

from __future__ import annotations

import logging
import socket
import concurrent.futures
from typing import Optional

logger = logging.getLogger(__name__)

TIMEOUT = 1.5  # seconds per port probe

COMMON_PORTS: dict[int, str] = {
    21:    "FTP",
    22:    "SSH",
    23:    "Telnet",
    25:    "SMTP",
    53:    "DNS",
    80:    "HTTP",
    110:   "POP3",
    143:   "IMAP",
    443:   "HTTPS",
    445:   "SMB",
    587:   "SMTP-Submission",
    993:   "IMAPS",
    995:   "POP3S",
    1433:  "MSSQL",
    3306:  "MySQL",
    3389:  "RDP",
    5432:  "PostgreSQL",
    5900:  "VNC",
    6379:  "Redis",
    8080:  "HTTP-Alt",
    8443:  "HTTPS-Alt",
    8888:  "HTTP-Dev",
    9200:  "Elasticsearch",
    11211: "Memcached",
    27017: "MongoDB",
}

# Per-port risk database: severity, OWASP category, CWEs, CVEs, recommendation
PORT_RISK_DB: dict[int, dict] = {
    21: {
        "severity": "HIGH",
        "owasp": "A02:2021-Cryptographic Failures",
        "cwes": ["CWE-319 Cleartext Transmission of Sensitive Information",
                 "CWE-287 Improper Authentication"],
        "cves": ["CVE-1999-0497 (anonymous FTP login allowed)",
                 "CVE-2010-4221 (ProFTPD stack overflow)"],
        "description": "FTP service exposed — credentials and data transmitted in cleartext.",
        "recommendation": "Disable FTP. Use SFTP (SSH port 22) or FTPS instead.",
    },
    22: {
        "severity": "MEDIUM",
        "owasp": "A07:2021-Identification and Authentication Failures",
        "cwes": ["CWE-287 Improper Authentication",
                 "CWE-307 Improper Restriction of Excessive Authentication Attempts"],
        "cves": ["CVE-2024-6387 (OpenSSH regreSSHion — unauthenticated RCE)",
                 "CVE-2023-38408 (OpenSSH ssh-agent RCE)"],
        "description": "SSH exposed to internet — ensure latest version and key-only auth.",
        "recommendation": "Disable password auth; require SSH keys; restrict source IPs; run latest OpenSSH.",
    },
    23: {
        "severity": "CRITICAL",
        "owasp": "A02:2021-Cryptographic Failures",
        "cwes": ["CWE-319 Cleartext Transmission of Sensitive Information",
                 "CWE-284 Improper Access Control"],
        "cves": ["CVE-1999-0246 (Telnet cleartext credentials)"],
        "description": "Telnet is open — all traffic including passwords is sent in cleartext.",
        "recommendation": "Disable Telnet immediately. Replace with SSH.",
    },
    25: {
        "severity": "MEDIUM",
        "owasp": "A05:2021-Security Misconfiguration",
        "cwes": ["CWE-183 Permissive List of Allowed Inputs",
                 "CWE-289 Authentication Bypass"],
        "cves": ["CVE-2002-1278 (open SMTP relay)"],
        "description": "SMTP port open — may allow open relay or email enumeration.",
        "recommendation": "Restrict SMTP relay; require authentication; use TLS (port 587).",
    },
    53: {
        "severity": "MEDIUM",
        "owasp": "A05:2021-Security Misconfiguration",
        "cwes": ["CWE-200 Exposure of Sensitive Information",
                 "CWE-346 Origin Validation Error"],
        "cves": ["CVE-2008-1447 (DNS cache poisoning — Kaminsky attack)",
                 "CVE-2020-1350 (SIGRed — Windows DNS RCE)"],
        "description": "DNS port open — check for zone transfer and cache poisoning vulnerabilities.",
        "recommendation": "Disable recursive queries for external clients; block zone transfers; enable DNSSEC.",
    },
    80: {
        "severity": "LOW",
        "owasp": "A02:2021-Cryptographic Failures",
        "cwes": ["CWE-319 Cleartext Transmission"],
        "cves": [],
        "description": "HTTP (unencrypted) is serving traffic — should redirect to HTTPS.",
        "recommendation": "Redirect all HTTP traffic to HTTPS. Add HSTS header.",
    },
    110: {
        "severity": "HIGH",
        "owasp": "A02:2021-Cryptographic Failures",
        "cwes": ["CWE-319 Cleartext Transmission of Sensitive Information"],
        "cves": ["CVE-2003-0297 (Courier POP3 buffer overflow)"],
        "description": "POP3 exposed — email credentials transmitted in cleartext.",
        "recommendation": "Use POP3S (port 995) with TLS. Disable plaintext POP3.",
    },
    143: {
        "severity": "HIGH",
        "owasp": "A02:2021-Cryptographic Failures",
        "cwes": ["CWE-319 Cleartext Transmission of Sensitive Information"],
        "cves": ["CVE-2021-38371 (Dovecot IMAP information disclosure)"],
        "description": "IMAP exposed — email credentials transmitted in cleartext.",
        "recommendation": "Use IMAPS (port 993) with TLS. Disable plaintext IMAP.",
    },
    445: {
        "severity": "CRITICAL",
        "owasp": "A06:2021-Vulnerable and Outdated Components",
        "cwes": ["CWE-94 Code Injection", "CWE-287 Improper Authentication"],
        "cves": ["CVE-2017-0144 (EternalBlue — WannaCry SMB RCE)",
                 "CVE-2020-0796 (SMBGhost — Windows SMB3 RCE)",
                 "CVE-2017-7494 (SambaCry — Linux SMB RCE)"],
        "description": "SMB port open to internet — historically the most exploited service.",
        "recommendation": "Block port 445 at the firewall immediately. Never expose SMB to the internet.",
    },
    1433: {
        "severity": "CRITICAL",
        "owasp": "A01:2021-Broken Access Control",
        "cwes": ["CWE-89 SQL Injection", "CWE-284 Improper Access Control"],
        "cves": ["CVE-2002-1123 (SQL Server buffer overflow)",
                 "CVE-2020-0618 (SSRS RCE)"],
        "description": "Microsoft SQL Server exposed to internet — database directly accessible.",
        "recommendation": "Block port 1433 at firewall. Use VPN or bastion host for DB access.",
    },
    3306: {
        "severity": "CRITICAL",
        "owasp": "A01:2021-Broken Access Control",
        "cwes": ["CWE-284 Improper Access Control", "CWE-89 SQL Injection"],
        "cves": ["CVE-2012-2122 (MySQL auth bypass)",
                 "CVE-2016-6662 (MySQL local privilege escalation)"],
        "description": "MySQL database port exposed to internet — database directly reachable.",
        "recommendation": "Block port 3306 at firewall. Bind MySQL to 127.0.0.1 only.",
    },
    3389: {
        "severity": "CRITICAL",
        "owasp": "A07:2021-Identification and Authentication Failures",
        "cwes": ["CWE-287 Improper Authentication", "CWE-94 Code Injection"],
        "cves": ["CVE-2019-0708 (BlueKeep — unauthenticated RCE via RDP)",
                 "CVE-2019-1182 (DejaBlue — RDP RCE)",
                 "CVE-2023-35352 (Windows RDP auth bypass)"],
        "description": "RDP exposed to internet — targeted by ransomware and brute-force attacks daily.",
        "recommendation": "Block RDP from internet. Use VPN or RD Gateway. Enable NLA.",
    },
    5432: {
        "severity": "CRITICAL",
        "owasp": "A01:2021-Broken Access Control",
        "cwes": ["CWE-284 Improper Access Control"],
        "cves": ["CVE-2019-9193 (PostgreSQL COPY TO/FROM PROGRAM — RCE)",
                 "CVE-2023-2454 (PostgreSQL privilege escalation)"],
        "description": "PostgreSQL database exposed to internet — direct database access possible.",
        "recommendation": "Block port 5432 at firewall. Bind PostgreSQL to localhost only.",
    },
    5900: {
        "severity": "CRITICAL",
        "owasp": "A07:2021-Identification and Authentication Failures",
        "cwes": ["CWE-287 Improper Authentication", "CWE-319 Cleartext Transmission"],
        "cves": ["CVE-2006-2369 (RealVNC auth bypass — no password needed)",
                 "CVE-2019-15681 (LibVNCServer memory leak)"],
        "description": "VNC remote desktop port exposed — often unauthenticated or weakly protected.",
        "recommendation": "Block VNC from internet. Tunnel over SSH if remote access is needed.",
    },
    6379: {
        "severity": "CRITICAL",
        "owasp": "A01:2021-Broken Access Control",
        "cwes": ["CWE-284 Improper Access Control", "CWE-306 Missing Authentication"],
        "cves": ["CVE-2022-0543 (Redis Lua sandbox escape — RCE)",
                 "CVE-2023-28425 (Redis integer overflow)"],
        "description": "Redis exposed with no authentication by default — full data read/write and potential RCE.",
        "recommendation": "Bind Redis to 127.0.0.1. Set requirepass. Block port 6379 at firewall.",
    },
    8080: {
        "severity": "MEDIUM",
        "owasp": "A05:2021-Security Misconfiguration",
        "cwes": ["CWE-16 Configuration"],
        "cves": [],
        "description": "Alternative HTTP port open — may expose dev/admin interface or proxy.",
        "recommendation": "Audit what service is running on 8080. Do not expose dev servers to the internet.",
    },
    8443: {
        "severity": "LOW",
        "owasp": "A05:2021-Security Misconfiguration",
        "cwes": ["CWE-16 Configuration"],
        "cves": [],
        "description": "Alternative HTTPS port open — audit what application is exposed here.",
        "recommendation": "Ensure the service on 8443 is hardened the same as the main HTTPS endpoint.",
    },
    8888: {
        "severity": "HIGH",
        "owasp": "A05:2021-Security Misconfiguration",
        "cwes": ["CWE-284 Improper Access Control"],
        "cves": [],
        "description": "Port 8888 open — commonly used by Jupyter Notebook, which has no auth by default.",
        "recommendation": "Block port 8888 from public internet. Require authentication on Jupyter.",
    },
    9200: {
        "severity": "CRITICAL",
        "owasp": "A01:2021-Broken Access Control",
        "cwes": ["CWE-306 Missing Authentication for Critical Function",
                 "CWE-284 Improper Access Control"],
        "cves": ["CVE-2014-3120 (Elasticsearch RCE via dynamic scripting)",
                 "CVE-2015-1427 (Elasticsearch Groovy sandbox escape — RCE)"],
        "description": "Elasticsearch REST API exposed — no authentication by default, full data access.",
        "recommendation": "Enable X-Pack security. Bind to localhost. Block port 9200 at firewall.",
    },
    11211: {
        "severity": "HIGH",
        "owasp": "A01:2021-Broken Access Control",
        "cwes": ["CWE-306 Missing Authentication", "CWE-400 Uncontrolled Resource Consumption"],
        "cves": ["CVE-2003-0244 (Memcached cache poisoning)"],
        "description": "Memcached exposed with no authentication — cache data readable and writable.",
        "recommendation": "Bind Memcached to 127.0.0.1. Block UDP 11211 (used in amplification DDoS).",
    },
    27017: {
        "severity": "CRITICAL",
        "owasp": "A01:2021-Broken Access Control",
        "cwes": ["CWE-306 Missing Authentication for Critical Function"],
        "cves": ["CVE-2013-4650 (MongoDB no auth by default)",
                 "CVE-2019-2389 (MongoDB privilege escalation)"],
        "description": "MongoDB exposed with no authentication by default — all databases accessible.",
        "recommendation": "Enable MongoDB authentication. Bind to localhost. Block port 27017 at firewall.",
    },
}


def _probe_port(host: str, port: int) -> tuple[int, bool, str]:
    """Return (port, is_open, banner). Non-blocking with TIMEOUT."""
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT) as s:
            s.settimeout(TIMEOUT)
            banner = ""
            try:
                # Send a generic probe to trigger a banner
                s.sendall(b"HEAD / HTTP/1.0\r\nHost: " + host.encode() + b"\r\n\r\n")
                data = s.recv(256)
                banner = data.decode("utf-8", errors="replace").split("\n")[0].strip()
            except Exception:
                # No banner is normal: plenty of services stay silent until
                # spoken to in their own protocol. The port is still open.
                logger.debug("No banner from %s:%s", host, port, exc_info=True)
            return port, True, banner
    except (socket.timeout, ConnectionRefusedError, OSError):
        return port, False, ""


# Ports a public website is expected to answer on. Reporting "443/HTTPS is
# open" against an HTTPS site is reporting that the website exists.
WEB_SERVICE_PORTS = frozenset({80, 443})

# CDNs publish these as alternate HTTP/HTTPS ports on every domain they front,
# so an open 8080/8443 behind a CDN says nothing about the origin.
CDN_ALTERNATE_PORTS = frozenset({8080, 8443})


def _cdn_alternate_risk(port: int, cdn: str) -> dict:
    """Reword an alternate-port finding that the CDN fully explains."""
    scheme = "HTTPS" if port == 8443 else "HTTP"
    return {
        "severity": "LOW",
        "owasp": "A05:2021-Security Misconfiguration",
        "cwes": ["CWE-16 Configuration"],
        "cves": [],
        "description": (
            f"Port {port} answers, but {cdn} publishes it as a standard "
            f"alternate {scheme} port on every domain it fronts. That is edge "
            f"behaviour, not evidence of a service exposed on the origin."
        ),
        "recommendation": (
            f"No action needed unless port {port} is also reachable directly on "
            f"the origin. Verify the origin is not addressable outside {cdn}."
        ),
    }


def scan_ports(host: str, skip_ports: "frozenset|set|tuple" = (),
               cdn: str | None = None) -> list[dict]:
    """
    Scan COMMON_PORTS on `host` in parallel.
    Returns a list of finding dicts for each open port.

    `skip_ports` suppresses ports whose exposure is the entire point of the
    target, such as 443 on a website. `cdn`, when the target is CDN-fronted,
    reclassifies the alternate ports that CDN publishes by default.
    """
    skip_ports = frozenset(skip_ports)

    # Resolve hostname once
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror as e:
        return [{"error": f"DNS resolution failed for {host}: {e}"}]

    open_ports: list[dict] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=40) as pool:
        futures = {pool.submit(_probe_port, ip, port): port for port in COMMON_PORTS}
        for future in concurrent.futures.as_completed(futures):
            port, is_open, banner = future.result()
            if not is_open or port in skip_ports:
                continue

            service = COMMON_PORTS[port]
            if cdn and port in CDN_ALTERNATE_PORTS:
                risk = _cdn_alternate_risk(port, cdn)
            else:
                risk = PORT_RISK_DB.get(port, {
                    "severity": "LOW",
                    "owasp": "A05:2021-Security Misconfiguration",
                    "cwes": ["CWE-16 Configuration"],
                    "cves": [],
                    "description": f"Port {port}/{service} is open and exposed to the internet.",
                    "recommendation": f"Audit whether port {port} needs to be publicly accessible.",
                })

            open_ports.append({
                "type": "port_exposure",
                "port": port,
                "service": service,
                "banner": banner or "—",
                "ip": ip,
                "severity": risk["severity"],
                "owasp_category": risk["owasp"],
                "cwes": risk["cwes"],
                "cves": risk["cves"],
                "description": risk["description"],
                "recommendation": risk["recommendation"],
                "rule_id": f"PORT-{port}",
                "file": f"{host}:{port}",
                "line": 0,
            })

    return sorted(open_ports, key=lambda x: (
        {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(x["severity"], 4),
        x["port"]
    ))
