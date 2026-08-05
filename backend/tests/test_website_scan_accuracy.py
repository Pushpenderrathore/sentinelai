"""
Regression tests for website-scan accuracy.

These come from a real false-positive report. Scanning a LinkedIn profile
produced 12 "vulnerabilities", including a HIGH "missing Content-Security-Policy"
against a site that ships one of the strictest CSPs on the web, a Flask code
patch for a company that does not run Flask, and "port 443 is open and exposed
to the internet" about an HTTPS website.

Root cause: the target returned HTTP 999 (bot block), and every check graded
that challenge page as if it were the application.
"""

from __future__ import annotations

import pytest

from agents import orchestrator
from tools import port_scanner, website_scanner


class _Resp:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, status_code=200, headers=None, text="", url="https://example.com"):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text
        self.content = text.encode()
        self.url = url
        self.cookies = []


# ── Block detection ──────────────────────────────────────────────────────────

class TestDetectBlock:
    def test_linkedin_999_is_a_block(self):
        """The exact status that produced the false report."""
        assert website_scanner.detect_block(_Resp(status_code=999)) is not None

    def test_rate_limit_is_a_block(self):
        assert website_scanner.detect_block(_Resp(status_code=429)) is not None

    def test_cloudflare_mitigated_header_is_a_block(self):
        resp = _Resp(status_code=403, headers={"cf-mitigated": "challenge"})
        assert "Cloudflare" in website_scanner.detect_block(resp)

    def test_datadome_header_is_a_block(self):
        resp = _Resp(status_code=403, headers={"x-datadome": "protected"})
        assert "DataDome" in website_scanner.detect_block(resp)

    def test_cloudflare_challenge_body_is_a_block(self):
        resp = _Resp(status_code=503, text="<html><title>Just a moment...</title>")
        assert website_scanner.detect_block(resp) is not None

    def test_403_from_a_cdn_is_a_block(self):
        resp = _Resp(status_code=403, headers={"server": "cloudflare"})
        assert "Cloudflare" in website_scanner.detect_block(resp)

    def test_normal_page_is_not_a_block(self):
        resp = _Resp(status_code=200, headers={"server": "nginx"}, text="<html>hello</html>")
        assert website_scanner.detect_block(resp) is None

    def test_ordinary_403_is_not_a_block(self):
        """A plain 403 from an origin is an access control result, not a WAF."""
        resp = _Resp(status_code=403, headers={"server": "nginx"}, text="Forbidden")
        assert website_scanner.detect_block(resp) is None


class TestDetectCdn:
    def test_cloudflare_by_server_header(self):
        assert website_scanner.detect_cdn({"server": "cloudflare"}) == "Cloudflare"

    def test_cloudflare_by_cf_ray(self):
        assert website_scanner.detect_cdn({"cf-ray": "abc123"}) == "Cloudflare"

    def test_fastly_by_x_served_by(self):
        assert website_scanner.detect_cdn({"x-served-by": "cache-fastly-1"}) == "Fastly"

    def test_plain_origin_has_no_cdn(self):
        assert website_scanner.detect_cdn({"server": "nginx/1.24"}) is None


class TestBlockedScanReportsNothing:
    def test_blocked_target_yields_only_a_block_notice(self, monkeypatch):
        monkeypatch.setattr(website_scanner, "assert_safe_target", lambda u: u)

        class _Session:
            headers = {}

            def get(self, *a, **k):
                return _Resp(status_code=999, headers={"server": "cloudflare"})

        monkeypatch.setattr(website_scanner.requests, "Session", lambda: _Session())

        meta = {}
        findings = website_scanner.scan_website("https://www.linkedin.com/in/someone", meta=meta)

        assert meta["blocked"] is not None
        assert len(findings) == 1
        assert findings[0]["type"] == "scan_blocked"
        # None of the header findings that made the original report wrong.
        joined = " ".join(f["description"] for f in findings)
        assert "Content-Security-Policy" not in joined
        assert "X-Frame-Options" not in joined


# ── Port findings ────────────────────────────────────────────────────────────

class TestPortFindings:
    def test_web_service_ports_are_the_website_not_a_finding(self):
        assert port_scanner.WEB_SERVICE_PORTS == frozenset({80, 443})

    def test_skipped_ports_produce_no_findings(self, monkeypatch):
        monkeypatch.setattr(port_scanner.socket, "gethostbyname", lambda h: "93.184.216.34")
        monkeypatch.setattr(port_scanner, "_probe_port",
                            lambda ip, port: (port, port in (80, 443), "HTTP/1.1 200 OK"))
        findings = port_scanner.scan_ports("example.com", skip_ports={80, 443})
        assert findings == []

    def test_cdn_alternate_ports_are_reworded(self, monkeypatch):
        monkeypatch.setattr(port_scanner.socket, "gethostbyname", lambda h: "93.184.216.34")
        monkeypatch.setattr(port_scanner, "_probe_port",
                            lambda ip, port: (port, port == 8443, "HTTP/1.1 400 Bad Request"))
        findings = port_scanner.scan_ports("example.com", cdn="Cloudflare")
        assert len(findings) == 1
        desc = findings[0]["description"]
        assert "Cloudflare" in desc
        assert "dev" not in desc.lower()      # no "may expose dev/admin interface"
        assert findings[0]["severity"] == "LOW"

    def test_alternate_ports_without_a_cdn_keep_the_original_warning(self, monkeypatch):
        monkeypatch.setattr(port_scanner.socket, "gethostbyname", lambda h: "10.0.0.1")
        monkeypatch.setattr(port_scanner, "_probe_port",
                            lambda ip, port: (port, port == 8080, ""))
        findings = port_scanner.scan_ports("origin.example.com", cdn=None)
        assert len(findings) == 1
        assert "Cloudflare" not in findings[0]["description"]


# ── Patch generation ─────────────────────────────────────────────────────────

class TestNoFabricatedPatches:
    """A website scan has no source code, so it must not emit a code diff."""

    VULN = {
        "id": "VULN-002",
        "file": "https://example.com/",
        "severity": "MEDIUM",
        "category": "A05:2021-Security Misconfiguration",
        "description": "Missing security header: X-Frame-Options",
    }

    def _run(self, monkeypatch, tech_stack, llm_reply):
        class _Response:
            content = llm_reply

        captured = {}

        def _fake_invoke(messages):
            captured["system"] = messages[0].content
            return _Response()

        monkeypatch.setattr(orchestrator, "invoke_llm", _fake_invoke)
        state = {"vulnerabilities": [self.VULN], "tech_stack": tech_stack}
        return orchestrator.fix_suggester_node(state), captured

    def test_website_patch_has_no_code_diff(self, monkeypatch):
        """Even if the model returns invented Flask code, it is stripped."""
        reply = ('{"vuln_id": "VULN-002", "file": "https://example.com/", '
                 '"original_code": "app = Flask(__name__)", '
                 '"patched_code": "app.config[\'X_FRAME_OPTIONS\'] = \'SAMEORIGIN\'", '
                 '"explanation": "adds the header"}')
        result, _ = self._run(monkeypatch, {"type": "website"}, reply)
        patch = result["patches"][0]
        assert "original_code" not in patch
        assert "patched_code" not in patch
        assert "Flask" not in json_dump(patch)

    def test_website_prompt_forbids_inventing_source(self, monkeypatch):
        reply = '{"vuln_id": "VULN-002", "remediation": "add header", "explanation": "x"}'
        _, captured = self._run(monkeypatch, {"type": "website"}, reply)
        assert "LIVE WEBSITE" in captured["system"]
        assert "Never invent source code" in captured["system"]

    def test_repo_scan_still_produces_a_code_diff(self, monkeypatch):
        reply = ('{"vuln_id": "VULN-002", "file": "app.py", '
                 '"original_code": "query(sql)", "patched_code": "query(sql, params)", '
                 '"explanation": "parameterised"}')
        result, captured = self._run(monkeypatch, {"languages": ["python"]}, reply)
        patch = result["patches"][0]
        assert patch["original_code"] == "query(sql)"
        assert patch["patched_code"] == "query(sql, params)"
        assert "LIVE WEBSITE" not in captured["system"]


def json_dump(obj) -> str:
    import json
    return json.dumps(obj)
