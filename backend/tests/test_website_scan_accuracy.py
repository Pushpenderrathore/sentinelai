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

    def test_github_pages_is_detected_as_fastly(self):
        """GitHub Pages hides Fastly: Server says GitHub.com, Via says varnish,
        and X-Served-By is an opaque cache id. Only the request-id header names it."""
        headers = {
            "server": "GitHub.com",
            "via": "1.1 varnish",
            "x-served-by": "cache-del-vibw2260028-DEL",
            "x-fastly-request-id": "f5a9ca60f958e7376eaa1f70daabdf64bbdd37db",
        }
        assert website_scanner.detect_cdn(headers) == "Fastly"

    def test_header_matching_is_case_insensitive(self):
        assert website_scanner.detect_cdn({"CF-RAY": "abc"}) == "Cloudflare"

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


# ── Policies delivered from the document ─────────────────────────────────────

class TestMetaDeliveredHeaders:
    """
    Static hosts cannot set response headers, so a site's only way to apply a
    CSP is a meta tag. The browser enforces it either way, so reporting it as
    missing is wrong. Found by fixing a real site and watching the scan still
    call it missing.
    """

    CSP_PAGE = ('<html><head><meta http-equiv="Content-Security-Policy" '
                'content="default-src \'self\'"></head><body>hi</body></html>')

    def test_csp_meta_tag_is_recognised(self):
        found = website_scanner.meta_delivered_headers(self.CSP_PAGE)
        assert found["content-security-policy"] == "default-src 'self'"

    def test_referrer_meta_tag_is_recognised(self):
        html = '<meta name="referrer" content="strict-origin-when-cross-origin">'
        found = website_scanner.meta_delivered_headers(html)
        assert found["referrer-policy"] == "strict-origin-when-cross-origin"

    def test_empty_content_is_not_a_policy(self):
        html = '<meta http-equiv="Content-Security-Policy" content="">'
        assert website_scanner.meta_delivered_headers(html) == {}

    def test_page_without_meta_policies(self):
        assert website_scanner.meta_delivered_headers("<html><head></head>") == {}

    def test_only_csp_and_referrer_may_come_from_markup(self):
        """Browsers ignore the others in a meta tag, so they must stay required."""
        assert website_scanner.META_DELIVERABLE_HEADERS == {
            "Content-Security-Policy", "Referrer-Policy"
        }

    def _scan(self, monkeypatch, body, headers):
        monkeypatch.setattr(website_scanner, "assert_safe_target", lambda u: u)

        class _Session:
            headers = {}

            def get(self, url, **k):
                if url.endswith("/"):
                    return _Resp(200, headers, body)
                return _Resp(404, {}, "")

        monkeypatch.setattr(website_scanner.requests, "Session", lambda: _Session())
        return website_scanner.scan_website("https://example.com/")

    def test_meta_csp_clears_the_missing_header_finding(self, monkeypatch):
        findings = self._scan(monkeypatch, self.CSP_PAGE, {"server": "GitHub.com"})
        assert not any("Missing security header: Content-Security-Policy" in f["description"]
                       for f in findings)

    def test_meta_csp_still_notes_the_frame_ancestors_limit(self, monkeypatch):
        findings = self._scan(monkeypatch, self.CSP_PAGE, {"server": "GitHub.com"})
        notes = [f for f in findings if "frame-ancestors" in f["description"]]
        assert len(notes) == 1
        assert notes[0]["severity"] == "LOW"

    def test_the_note_cannot_be_read_as_a_missing_csp(self, monkeypatch):
        """
        The report summariser inverted the earlier wording into "Implement
        Content-Security-Policy" on a site that already had one. The finding
        must say the policy is present before it says what it cannot do.
        """
        findings = self._scan(monkeypatch, self.CSP_PAGE, {"server": "GitHub.com"})
        note = next(f for f in findings if "frame-ancestors" in f["description"])
        description = note["description"].lower()
        assert "is present and enforced" in description
        assert description.index("present") < description.index("inactive")
        assert "missing" not in description
        assert "no csp needs to be written" in note["code"].lower()

    def test_a_meta_tag_does_not_satisfy_x_frame_options(self, monkeypatch):
        """X-Frame-Options in a meta tag is ignored by browsers, so it stays missing."""
        html = ('<meta http-equiv="X-Frame-Options" content="DENY">'
                + self.CSP_PAGE)
        findings = self._scan(monkeypatch, html, {"server": "GitHub.com"})
        assert any("Missing security header: X-Frame-Options" in f["description"]
                   for f in findings)

    def test_real_header_takes_precedence_and_adds_no_note(self, monkeypatch):
        findings = self._scan(
            monkeypatch, "<html></html>",
            {"content-security-policy": "default-src 'self'", "server": "nginx"},
        )
        assert not any("Content-Security-Policy" in f["description"] for f in findings)


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

    def _run(self, monkeypatch, tech_stack, llm_reply, vuln=None, repo_path=""):
        class _Response:
            content = llm_reply

        captured = {}

        def _fake_invoke(messages):
            captured["system"] = messages[0].content
            return _Response()

        monkeypatch.setattr(orchestrator, "invoke_llm", _fake_invoke)
        state = {"vulnerabilities": [vuln or self.VULN], "tech_stack": tech_stack,
                 "repo_path": repo_path}
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

    def test_repo_scan_still_produces_a_code_diff(self, monkeypatch, tmp_path):
        (tmp_path / "app.py").write_text(
            "import sqlite3\n\n\ndef search(sql):\n    return query(sql)\n"
        )
        reply = ('{"vuln_id": "VULN-002", "file": "app.py", '
                 '"original_code": "return query(sql)", '
                 '"patched_code": "return query(sql, params)", '
                 '"explanation": "parameterised"}')
        result, captured = self._run(
            monkeypatch, {"languages": ["python"]}, reply,
            vuln={"id": "VULN-002", "file": "app.py", "line": 5, "severity": "MEDIUM",
                  "category": "A03:2021-Injection", "description": "SQL injection"},
            repo_path=str(tmp_path),
        )
        patch = result["patches"][0]
        assert patch["patched_code"] == "return query(sql, params)"
        assert "LIVE WEBSITE" not in captured["system"]


# ── Patches are diffed against the real file ─────────────────────────────────

class TestPatchesUseRealSource:
    """
    The fix suggester was given only a finding's metadata, never the source, so
    it invented the code it claimed to patch. On a real scan it emitted
    "ws = new WebSocket('ws://example.com/path')" for frontend/lib/ws.ts:14 —
    a line that is not in that file, on a finding that Semgrep had matched
    inside a JSDoc comment. The repository is already cloned, so the flagged
    line is a fact to read, not something to ask a model about.
    """

    from agents import orchestrator as _orch

    def _fix(self, monkeypatch, tmp_path, reply, line=5):
        (tmp_path / "app.py").write_text(
            "import os\n"
            "\n"
            "\n"
            "def run(cmd):\n"
            "    os.system(cmd)\n"
            "\n"
            "\n"
            "def done():\n"
            "    return True\n"
        )
        captured = {}

        class _Response:
            content = reply

        def _fake_invoke(messages):
            captured["human"] = messages[1].content
            return _Response()

        monkeypatch.setattr(self._orch, "invoke_llm", _fake_invoke)
        state = {
            "vulnerabilities": [{"id": "VULN-001", "file": "app.py", "line": line,
                                 "severity": "HIGH", "category": "A03:2021-Injection",
                                 "description": "Shell injection via os.system"}],
            "tech_stack": {"languages": ["python"]},
            "repo_path": str(tmp_path),
        }
        return self._orch.fix_suggester_node(state), captured

    REPLY = ('{"vuln_id": "VULN-001", "file": "app.py", '
             '"original_code": "os.system(user_input)  # invented", '
             '"patched_code": "subprocess.run([cmd], shell=False)", '
             '"explanation": "avoids the shell"}')

    def test_the_real_source_is_shown_to_the_model(self, monkeypatch, tmp_path):
        _, captured = self._fix(monkeypatch, tmp_path, self.REPLY)
        assert "os.system(cmd)" in captured["human"]
        assert "def run(cmd):" in captured["human"], "context lines are included"

    def test_the_flagged_line_is_marked(self, monkeypatch, tmp_path):
        _, captured = self._fix(monkeypatch, tmp_path, self.REPLY)
        assert "    5 >|     os.system(cmd)" in captured["human"]

    def test_invented_original_code_is_replaced_by_the_real_line(self, monkeypatch, tmp_path):
        result, _ = self._fix(monkeypatch, tmp_path, self.REPLY)
        patch = result["patches"][0]
        assert patch["original_code"] == "    os.system(cmd)"
        assert "invented" not in patch["original_code"]

    def test_the_models_fix_is_kept(self, monkeypatch, tmp_path):
        result, _ = self._fix(monkeypatch, tmp_path, self.REPLY)
        assert result["patches"][0]["patched_code"] == "subprocess.run([cmd], shell=False)"

    def test_the_excerpt_gutter_is_stripped_from_the_fix(self, monkeypatch, tmp_path):
        """
        Observed live: the model copied the excerpt's ">" marker into its
        answer, so the report showed '>       - uses: actions/checkout@...'
        as the patched code.
        """
        reply = ('{"vuln_id": "VULN-001", "file": "app.py", '
                 '"patched_code": ">     subprocess.run([cmd], shell=False)", '
                 '"explanation": "x"}')
        result, _ = self._fix(monkeypatch, tmp_path, reply)
        assert result["patches"][0]["patched_code"] == "    subprocess.run([cmd], shell=False)"

    def test_numbered_gutter_is_stripped_too(self, monkeypatch, tmp_path):
        reply = ('{"vuln_id": "VULN-001", "file": "app.py", '
                 '"patched_code": "    5 >|     safe(cmd)", "explanation": "x"}')
        result, _ = self._fix(monkeypatch, tmp_path, reply)
        assert result["patches"][0]["patched_code"] == "    safe(cmd)"

    def test_an_unreadable_file_yields_no_diff_at_all(self, monkeypatch, tmp_path):
        """Nothing to verify against, so no diff may be presented as verified."""
        result, _ = self._fix(monkeypatch, tmp_path, self.REPLY, line=999)
        patch = result["patches"][0]
        assert "original_code" not in patch
        assert "patched_code" not in patch
        assert "Could not read" in patch["explanation"]

    def test_paths_outside_the_clone_are_refused(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1\n")
        assert self._orch.read_source_window(str(tmp_path), "../../etc/passwd", 1) is None

    def test_missing_file_returns_nothing(self, tmp_path):
        assert self._orch.read_source_window(str(tmp_path), "nope.py", 1) is None

    def test_line_past_the_end_returns_nothing(self, tmp_path):
        (tmp_path / "app.py").write_text("x = 1\n")
        assert self._orch.read_source_window(str(tmp_path), "app.py", 40) is None

    def test_reads_the_exact_line(self, tmp_path):
        (tmp_path / "app.py").write_text("a\nb\nTARGET\nd\n")
        _, exact = self._orch.read_source_window(str(tmp_path), "app.py", 3)
        assert exact == "TARGET"


# ── CORS context ─────────────────────────────────────────────────────────────

class TestWildcardCorsIsGradedInContext:
    """
    "Access-Control-Allow-Origin: *" was graded HIGH on the header alone, which
    reported "allows any origin to read API responses" against a static
    portfolio with no API. It was also the only HIGH, so it set the risk
    floor and drove most of the score.

    The wildcard only discloses something when the response carries data the
    caller is not already entitled to. On a public document it discloses
    nothing, because a direct GET returns the same bytes.
    """

    # Matches the real demo target: GitHub Pages ships HSTS and the site
    # applies its CSP from the document, so CORS was the only HIGH left.
    PAGE = ('<html><head><meta http-equiv="Content-Security-Policy" '
            'content="default-src \'self\'"></head><body>hi</body></html>')

    def _scan(self, monkeypatch, headers):
        monkeypatch.setattr(website_scanner, "assert_safe_target", lambda u: u)

        class _Session:
            headers = {}

            def get(self, url, **k):
                if url.endswith("/"):
                    return _Resp(200, headers, TestWildcardCorsIsGradedInContext.PAGE)
                return _Resp(404, {}, "")

        monkeypatch.setattr(website_scanner.requests, "Session", lambda: _Session())
        return website_scanner.scan_website("https://example.com/")

    def _cors(self, findings):
        return [f for f in findings if "CORS" in f["description"]]

    def test_public_static_content_is_low_not_high(self, monkeypatch):
        findings = self._scan(monkeypatch, {"access-control-allow-origin": "*",
                                            "server": "GitHub.com"})
        cors = self._cors(findings)
        assert len(cors) == 1
        assert cors[0]["severity"] == "LOW"
        assert "already publicly readable" in cors[0]["description"]

    def test_no_high_finding_remains_on_a_static_portfolio(self, monkeypatch):
        """The whole point: this target should not carry a HIGH."""
        findings = self._scan(monkeypatch, {
            "access-control-allow-origin": "*",
            "server": "GitHub.com",
            "strict-transport-security": "max-age=31536000",
        })
        assert not [f for f in findings if f["severity"] == "HIGH"]

    def test_credentialed_wildcard_is_still_high(self, monkeypatch):
        cors = self._cors(self._scan(monkeypatch, {
            "access-control-allow-origin": "*",
            "access-control-allow-credentials": "true",
        }))
        assert cors[0]["severity"] == "HIGH"

    def test_cookie_bearing_response_is_medium(self, monkeypatch):
        cors = self._cors(self._scan(monkeypatch, {
            "access-control-allow-origin": "*",
            "set-cookie": "session=abc",
        }))
        assert cors[0]["severity"] == "MEDIUM"

    def test_no_wildcard_means_no_finding(self, monkeypatch):
        cors = self._cors(self._scan(monkeypatch, {
            "access-control-allow-origin": "https://trusted.example",
        }))
        assert cors == []

    def test_the_low_note_names_where_the_header_came_from(self, monkeypatch):
        cors = self._cors(self._scan(monkeypatch, {"access-control-allow-origin": "*",
                                                   "server": "GitHub.com"}))
        assert "GitHub Pages" in cors[0]["code"]


# ── Unfixable-on-this-host findings ──────────────────────────────────────────

class TestStaticHostCannotSetHeaders:
    """
    GitHub Pages cannot set a response header at all, so "add X-Frame-Options"
    is advice the owner cannot act on and the fix suggester answers it with
    nginx config for a server that does not exist. The finding stays (visitors
    really are unprotected) but it has to say so and give a real remediation.
    """

    def _scan(self, monkeypatch, headers, body="<html><body>hi</body></html>"):
        monkeypatch.setattr(website_scanner, "assert_safe_target", lambda u: u)

        class _Session:
            headers = {}

            def get(self, url, **k):
                if url.endswith("/"):
                    return _Resp(200, headers, body)
                return _Resp(404, {}, "")

        monkeypatch.setattr(website_scanner.requests, "Session", lambda: _Session())
        return website_scanner.scan_website("https://example.com/")

    def test_github_pages_is_detected(self):
        assert website_scanner.detect_static_host({"server": "GitHub.com"}) == "GitHub Pages"

    def test_an_ordinary_server_is_not_flagged(self):
        assert website_scanner.detect_static_host({"server": "nginx/1.25"}) is None

    def test_the_constraint_is_in_the_description(self, monkeypatch):
        """The summariser and fix suggester only ever see the description."""
        findings = self._scan(monkeypatch, {"server": "GitHub.com"})
        xfo = next(f for f in findings if "X-Frame-Options" in f["description"])
        assert "GitHub Pages cannot set response headers" in xfo["description"]

    def test_the_evidence_names_a_remediation_that_works(self, monkeypatch):
        findings = self._scan(monkeypatch, {"server": "GitHub.com"})
        xfo = next(f for f in findings if "X-Frame-Options" in f["description"])
        assert "Cloudflare" in xfo["code"]

    def test_severity_is_unchanged(self, monkeypatch):
        """Visitors are unprotected either way — being unable to fix it is not a downgrade."""
        findings = self._scan(monkeypatch, {"server": "GitHub.com"})
        xfo = next(f for f in findings if "X-Frame-Options" in f["description"])
        assert xfo["severity"] == "MEDIUM"

    def test_an_ordinary_host_gets_no_platform_note(self, monkeypatch):
        findings = self._scan(monkeypatch, {"server": "nginx/1.25"})
        xfo = next(f for f in findings if "X-Frame-Options" in f["description"])
        assert "cannot set response headers" not in xfo["description"]

    def test_meta_deliverable_headers_get_no_platform_note(self, monkeypatch):
        """A meta tag IS the fix for CSP, so the host is not the blocker."""
        findings = self._scan(monkeypatch, {"server": "GitHub.com"})
        csp = next(f for f in findings if "Content-Security-Policy" in f["description"])
        assert "cannot set response headers" not in csp["description"]


# ── Remediation for headers the host cannot set ──────────────────────────────

class TestStaticHostRemediationIsNotAskedOfTheModel:
    """
    Asked to fix a missing header on GitHub Pages, the model answered "add the
    following header in the GitHub Pages settings" — a settings page that does
    not exist. The remediation depends only on the platform, so it is a fact to
    state, not a question to ask.
    """

    from agents import orchestrator as _orch

    VULN = {"id": "VULN-002", "file": "https://example.com/", "severity": "MEDIUM",
            "description": "Missing security header: X-Frame-Options "
                           "(GitHub Pages cannot set response headers)"}

    def test_returns_a_patch_without_calling_the_model(self):
        patch = self._orch._header_remediation_for_static_host(self.VULN, "GitHub Pages")
        assert patch["source"] == "platform-constraint"
        assert patch["vuln_id"] == "VULN-002"

    def test_names_a_route_that_actually_works(self):
        patch = self._orch._header_remediation_for_static_host(self.VULN, "GitHub Pages")
        assert "Cloudflare" in patch["remediation"]
        assert "Not fixable on GitHub Pages" in patch["remediation"]

    def test_says_a_meta_tag_will_not_work(self):
        """The obvious wrong workaround, which browsers ignore."""
        patch = self._orch._header_remediation_for_static_host(self.VULN, "GitHub Pages")
        assert "meta tag is not a substitute" in patch["explanation"]

    def test_ordinary_hosts_still_go_to_the_model(self):
        assert self._orch._header_remediation_for_static_host(self.VULN, None) is None

    def test_csp_is_not_treated_as_platform_blocked(self):
        """A meta tag is a real fix for CSP, so the model should answer it."""
        vuln = dict(self.VULN, description="Missing security header: Content-Security-Policy")
        assert self._orch._header_remediation_for_static_host(vuln, "GitHub Pages") is None

    def test_non_header_findings_are_untouched(self):
        vuln = dict(self.VULN, description="Wildcard CORS policy on public content")
        assert self._orch._header_remediation_for_static_host(vuln, "GitHub Pages") is None

    def test_fix_suggester_uses_it_and_skips_the_llm(self, monkeypatch):
        called = []

        class _Response:
            content = '{"vuln_id": "VULN-002", "remediation": "invented"}'

        def _spy(messages):
            called.append(1)
            return _Response()

        monkeypatch.setattr(self._orch, "invoke_llm", _spy)
        result = self._orch.fix_suggester_node({
            "vulnerabilities": [self.VULN],
            "tech_stack": {"type": "website", "static_host": "GitHub Pages"},
            "scan_id": "t",
        })
        assert called == [], "the model must not be asked"
        assert result["patches"][0]["source"] == "platform-constraint"
        assert any("cannot be fixed on GitHub Pages" in line
                   for line in result["agent_logs"])


def json_dump(obj) -> str:
    import json
    return json.dumps(obj)
