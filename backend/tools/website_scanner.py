"""
HTTP-based security scanner for websites.
Checks security headers, SSL cert, exposed files, CORS, cookies, and server info.
"""

from __future__ import annotations

import re
import secrets
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

# ── Sensitive-file detection ──────────────────────────────────────────────────
# A path returning HTTP 200 is NOT evidence of exposure on its own — soft-404
# pages, catch-all SPA routes, and CDNs return 200 + HTML for any path, and some
# files (crossdomain.xml) are public by design. Each path therefore carries a
# validator that confirms the response body actually matches the file's
# signature before it is reported.

def _looks_html(resp) -> bool:
    ct = resp.headers.get("content-type", "").lower()
    if "html" in ct:
        return True
    head = resp.content[:512].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html")


def _v_env(r) -> bool:
    return not _looks_html(r) and re.search(r"(?m)^[A-Z][A-Z0-9_]*\s*=", r.text[:4000]) is not None

def _v_git_config(r) -> bool:
    t = r.text[:2000].lower()
    return "[core]" in t or "repositoryformatversion" in t

def _v_git_head(r) -> bool:
    t = r.text[:200].strip().lower()
    return t.startswith("ref:") or re.fullmatch(r"[0-9a-f]{40}", t) is not None

def _v_php_source(r) -> bool:
    # Only a leak if raw PHP source comes back (server failed to execute it)
    return "<?php" in r.text[:4000]

def _v_phpinfo(r) -> bool:
    t = r.text[:4000]
    return "phpinfo()" in t or "PHP Version" in t

def _v_server_status(r) -> bool:
    t = r.text[:3000]
    return any(k in t for k in ("Apache Server Status", "Apache Server Information", "Server Version:"))

def _v_htaccess(r) -> bool:
    if _looks_html(r):
        return False
    t = r.text[:2000]
    return any(k in t for k in ("RewriteEngine", "RewriteRule", "AuthType", "<Files", "Order ", "Require "))

def _v_sql_dump(r) -> bool:
    if _looks_html(r):
        return False
    t = r.text[:4000].upper()
    return any(k in t for k in ("INSERT INTO", "CREATE TABLE", "DROP TABLE", "MYSQL DUMP", "POSTGRESQL"))

def _v_swagger_json(r) -> bool:
    if "json" not in r.headers.get("content-type", "").lower() and not r.text[:50].lstrip().startswith("{"):
        return False
    t = r.text[:2000].lower()
    return '"swagger"' in t or '"openapi"' in t or '"paths"' in t

def _v_swagger_ui(r) -> bool:
    return "swagger-ui" in r.text[:5000].lower()

def _v_ds_store(r) -> bool:
    return b"Bud1" in r.content[:8] or r.content[:4] == b"\x00\x00\x00\x01"

def _v_login_panel(r) -> bool:
    # A real admin/login panel serves a password input. Generic words like
    # "login"/"username" appear on countless normal pages (and frameworks route
    # unknown paths to profile pages), so require an actual password field.
    if not _looks_html(r):
        return False
    return re.search(r'''<input[^>]+type\s*=\s*["']password["']''', r.text[:20000], re.I) is not None

def _v_phpmyadmin(r) -> bool:
    # phpMyAdmin login page is unmistakable
    return "phpmyadmin" in r.text[:8000].lower() and _v_login_panel(r)

def _v_crossdomain(r) -> bool:
    # Public by design — only a misconfiguration if it trusts ANY origin via a
    # bare domain="*". Subdomain wildcards like "*.example.com" are legitimate
    # scoping and must NOT match.
    return re.search(r'''allow-access-from\s+domain\s*=\s*(["'])\*\1''', r.text[:4000]) is not None


# (path, severity, validator, human-readable label)
SENSITIVE_PATHS = [
    ("/.env",             "CRITICAL", _v_env,          "Environment file with secrets exposed"),
    ("/.git/config",      "CRITICAL", _v_git_config,   ".git repository config exposed (source disclosure)"),
    ("/.git/HEAD",        "HIGH",     _v_git_head,     ".git metadata exposed (repo may be downloadable)"),
    ("/config.php",       "CRITICAL", _v_php_source,   "Raw PHP config source exposed"),
    ("/wp-config.php",    "CRITICAL", _v_php_source,   "Raw WordPress config source exposed (DB credentials)"),
    ("/phpinfo.php",      "HIGH",     _v_phpinfo,      "phpinfo() page exposes server configuration"),
    ("/server-status",    "MEDIUM",   _v_server_status,"Apache server-status page publicly accessible"),
    ("/server-info",      "MEDIUM",   _v_server_status,"Apache server-info page publicly accessible"),
    ("/.htaccess",        "HIGH",     _v_htaccess,     "Apache .htaccess file exposed"),
    ("/backup.sql",       "CRITICAL", _v_sql_dump,     "Database backup (SQL dump) publicly downloadable"),
    ("/dump.sql",         "CRITICAL", _v_sql_dump,     "Database dump (SQL) publicly downloadable"),
    ("/database.sql",     "CRITICAL", _v_sql_dump,     "Database file (SQL) publicly downloadable"),
    ("/api/swagger.json", "LOW",      _v_swagger_json, "API schema (Swagger) publicly exposed"),
    ("/api/openapi.json", "LOW",      _v_swagger_json, "API schema (OpenAPI) publicly exposed"),
    ("/swagger-ui.html",  "LOW",      _v_swagger_ui,   "Swagger UI publicly accessible"),
    ("/.DS_Store",        "LOW",      _v_ds_store,     ".DS_Store exposes a directory file listing"),
    ("/crossdomain.xml",  "MEDIUM",   _v_crossdomain,  "crossdomain.xml trusts ANY origin (wildcard)"),
    ("/admin",            "LOW",      _v_login_panel,  "Admin login panel reachable"),
    ("/administrator",    "LOW",      _v_login_panel,  "Administrator login panel reachable"),
    ("/wp-admin",         "LOW",      _v_login_panel,  "WordPress admin panel reachable"),
    ("/phpmyadmin",       "LOW",      _v_phpmyadmin,   "phpMyAdmin panel reachable"),
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
    # Baseline: many sites return 200 + HTML for any path (soft-404 / catch-all).
    # Capture the response to a guaranteed-missing path so we can tell a real
    # file apart from the generic page.
    baseline = None
    try:
        baseline = http.get(f"{base_url}/sentinel-probe-{secrets.token_hex(8)}",
                            timeout=6, allow_redirects=False, verify=False)
    except RequestException:
        pass

    for path, sev, validator, label in SENSITIVE_PATHS:
        try:
            r = http.get(f"{base_url}{path}", timeout=6, allow_redirects=False, verify=False)
        except RequestException:
            continue
        if r.status_code not in (200, 206):
            continue
        # Same size as the catch-all page → it IS the catch-all page, not the file
        if (baseline is not None and baseline.status_code in (200, 206)
                and abs(len(r.content) - len(baseline.content)) <= 16):
            continue
        # Body must actually match the file's signature
        try:
            if not validator(r):
                continue
        except Exception:
            continue
        findings.append(_f(f"{base_url}{path}", sev,
                          "A05:2021-Security Misconfiguration",
                          f"{label}: {path} (HTTP {r.status_code})",
                          f"GET {path} → {r.status_code} "
                          f"({len(r.content)} bytes, {r.headers.get('content-type', '?')})"))

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
                    # Modern certs are short-lived and auto-renew (Let's Encrypt
                    # 90-day, etc.), so a cert 2+ weeks out is normal — only warn
                    # when expiry is genuinely imminent to avoid false alarms.
                    if days_left < 0:
                        findings.append(_f(url, "CRITICAL", "A02:2021-Cryptographic Failures",
                                          f"SSL certificate has EXPIRED ({abs(days_left)} days ago)",
                                          f"notAfter: {expires_str}"))
                    elif days_left < 14:
                        sev = "HIGH" if days_left < 3 else "MEDIUM"
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
