"""
HTTP-based security scanner for websites.
Checks security headers, SSL cert, exposed files, CORS, cookies, and server info.
"""

from __future__ import annotations

import socket
import ssl
import urllib.parse
from datetime import datetime, timezone

import requests
import urllib3
from requests.exceptions import RequestException

from .url_guard import assert_safe_target

# Probes against scan targets intentionally use verify=False — silence the noise
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SENSITIVE_PATHS = [
    "/.env",
    "/.git/config",
    "/.git/HEAD",
    "/config.php",
    "/wp-config.php",
    "/phpinfo.php",
    "/server-status",
    "/server-info",
    "/.htaccess",
    "/admin",
    "/administrator",
    "/wp-admin",
    "/phpmyadmin",
    "/backup.sql",
    "/dump.sql",
    "/database.sql",
    "/api/swagger.json",
    "/api/openapi.json",
    "/swagger-ui.html",
    "/.DS_Store",
    "/crossdomain.xml",
]

SECURITY_HEADERS = {
    "Strict-Transport-Security":    ("HIGH",   "A02:2021-Cryptographic Failures"),
    "Content-Security-Policy":      ("HIGH",   "A05:2021-Security Misconfiguration"),
    "X-Frame-Options":              ("MEDIUM", "A05:2021-Security Misconfiguration"),
    "X-Content-Type-Options":       ("MEDIUM", "A05:2021-Security Misconfiguration"),
    "Referrer-Policy":              ("LOW",    "A05:2021-Security Misconfiguration"),
    "Permissions-Policy":           ("LOW",    "A05:2021-Security Misconfiguration"),
}

_HEADERS = {"User-Agent": "SentinelAI-SecurityScanner/1.0"}


def is_github_url(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host == "github.com"


def scan_website(url: str) -> list[dict]:
    # Re-validate at scan time — blocks SSRF against internal hosts even if
    # the caller skipped the request-level check.
    url = assert_safe_target(url)

    parsed = urllib.parse.urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    findings: list[dict] = []
    http = requests.Session()
    http.headers.update(_HEADERS)

    # ── 1. Fetch root page ──────────────────────────────────────────────────
    try:
        resp = http.get(url, timeout=15, allow_redirects=True, verify=True)
    except requests.exceptions.SSLError:
        findings.append(_f(url, "CRITICAL", "A02:2021-Cryptographic Failures",
                          "SSL/TLS certificate is invalid or self-signed",
                          "HTTPS handshake failed — browser would show security warning"))
        try:
            resp = http.get(url, timeout=15, allow_redirects=True, verify=False)
        except RequestException as e:
            findings.append(_f(url, "HIGH", "connectivity",
                              f"Could not reach website: {e}", ""))
            return findings
    except RequestException as e:
        findings.append(_f(url, "HIGH", "connectivity",
                          f"Could not reach website: {e}", ""))
        return findings

    hdrs = {k.lower(): v for k, v in resp.headers.items()}

    # ── 2. HTTP (no TLS) ────────────────────────────────────────────────────
    if parsed.scheme == "http":
        findings.append(_f(url, "HIGH", "A02:2021-Cryptographic Failures",
                          "Site served over plain HTTP — all traffic is unencrypted",
                          f"URL scheme: {parsed.scheme}"))

    # ── 3. Missing security headers ─────────────────────────────────────────
    for header, (sev, cat) in SECURITY_HEADERS.items():
        if header.lower() not in hdrs:
            findings.append(_f(url, sev, cat,
                              f"Missing security header: {header}",
                              f"HTTP response has no {header} header"))

    # ── 4. Server / technology info disclosure ──────────────────────────────
    for h in ("server", "x-powered-by", "x-aspnet-version", "x-aspnetmvc-version"):
        if h in hdrs:
            findings.append(_f(url, "LOW", "A05:2021-Security Misconfiguration",
                              f"Server information disclosed via '{h}': {hdrs[h]}",
                              f"{h}: {hdrs[h]}"))

    # ── 5. HSTS strength ────────────────────────────────────────────────────
    hsts = hdrs.get("strict-transport-security", "")
    if hsts:
        try:
            parts = {p.strip().split("=")[0].strip(): p.strip().split("=")[1].strip()
                     for p in hsts.split(";") if "=" in p}
            max_age = int(parts.get("max-age", "0"))
            if max_age < 31_536_000:
                findings.append(_f(url, "LOW", "A02:2021-Cryptographic Failures",
                                  f"HSTS max-age too short ({max_age}s) — recommend ≥ 31536000",
                                  f"Strict-Transport-Security: {hsts}"))
        except (ValueError, IndexError):
            pass

    # ── 6. CORS wildcard ────────────────────────────────────────────────────
    if hdrs.get("access-control-allow-origin") == "*":
        findings.append(_f(url, "HIGH", "A05:2021-Security Misconfiguration",
                          "Wildcard CORS policy allows any origin to read API responses",
                          "Access-Control-Allow-Origin: *"))

    # ── 7. Dangerous HTTP methods ───────────────────────────────────────────
    allow = hdrs.get("allow", "")
    for method in ("TRACE", "PUT", "DELETE"):
        if method in allow:
            findings.append(_f(url, "MEDIUM", "A05:2021-Security Misconfiguration",
                              f"Dangerous HTTP method enabled: {method}",
                              f"Allow: {allow}"))

    # ── 8. Cookie security flags ────────────────────────────────────────────
    for cookie in resp.cookies:
        issues = []
        if not cookie.secure:
            issues.append("missing Secure flag")
        if "httponly" not in [a.lower() for a in (cookie._rest or {})]:
            issues.append("missing HttpOnly flag")
        if "samesite" not in [a.lower() for a in (cookie._rest or {})]:
            issues.append("missing SameSite attribute")
        if issues:
            findings.append(_f(url, "MEDIUM", "A05:2021-Security Misconfiguration",
                              f"Insecure cookie '{cookie.name}': {', '.join(issues)}",
                              f"Set-Cookie: {cookie.name}=..."))

    # ── 9. Sensitive file exposure ───────────────────────────────────────────
    critical_paths = {"/.env", "/.git/config", "/wp-config.php",
                      "/backup.sql", "/dump.sql", "/database.sql"}
    for path in SENSITIVE_PATHS:
        try:
            r = http.get(f"{base_url}{path}", timeout=6, allow_redirects=False,
                         verify=False)
            if r.status_code in (200, 206):
                sev = "CRITICAL" if path in critical_paths else "HIGH"
                findings.append(_f(f"{base_url}{path}", sev,
                                  "A05:2021-Security Misconfiguration",
                                  f"Sensitive file publicly accessible: {path} (HTTP {r.status_code})",
                                  f"GET {path} → {r.status_code} ({len(r.content)} bytes)"))
        except RequestException:
            pass

    # ── 10. SSL certificate expiry ───────────────────────────────────────────
    if parsed.scheme == "https":
        try:
            ctx = ssl.create_default_context()
            with ctx.wrap_socket(socket.socket(), server_hostname=parsed.hostname) as s:
                s.settimeout(5)
                s.connect((parsed.hostname, parsed.port or 443))
                cert = s.getpeercert()
                expires_str = cert.get("notAfter", "")
                if expires_str:
                    expires = datetime.strptime(expires_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                    days_left = (expires - datetime.now(timezone.utc)).days
                    if days_left < 30:
                        sev = "CRITICAL" if days_left < 7 else "HIGH"
                        findings.append(_f(url, sev, "A02:2021-Cryptographic Failures",
                                          f"SSL certificate expires in {days_left} days",
                                          f"notAfter: {expires_str}"))
        except Exception:
            pass

    return findings


def _f(file: str, severity: str, category: str,
       description: str, code: str) -> dict:
    return {
        "source":      "website",
        "file":        file,
        "line":        0,
        "severity":    severity,
        "category":    category,
        "description": description,
        "code":        code,
    }
