"""
Regression tests for the way LLM output is turned into vulnerabilities.

These cover a real incident: scanning a repository where Bandit reported 18
issues and Semgrep 28 produced a report saying "no vulnerabilities, indicating
a secure codebase". The model had prefixed its JSON with a sentence of prose,
parsing failed, and the empty-list fallback rendered as a clean report.

The invariant these tests protect: the LLM may enrich findings, but it must
never be able to remove them.
"""

from __future__ import annotations

import pytest

from agents import orchestrator


# ── _parse_json ──────────────────────────────────────────────────────────────

class TestParseJson:
    def test_plain_array(self):
        assert orchestrator._parse_json('[{"id": "V1"}]', "FB") == [{"id": "V1"}]

    def test_prose_preamble_then_fenced_json(self):
        """The exact shape that caused the incident."""
        raw = (
            "Here are the vulnerability objects mapped from the raw static "
            "analysis findings:\n\n```json\n[{\"id\": \"V1\"}]\n```"
        )
        assert orchestrator._parse_json(raw, "FB") == [{"id": "V1"}]

    def test_prose_on_both_sides(self):
        raw = 'Sure! [{"id": "V2"}] hope that helps.'
        assert orchestrator._parse_json(raw, "FB") == [{"id": "V2"}]

    def test_bare_fence_without_language(self):
        raw = "```\n[{\"id\": \"V3\"}]\n```"
        assert orchestrator._parse_json(raw, "FB") == [{"id": "V3"}]

    def test_literal_newlines_inside_a_string_value(self):
        """
        Observed from the exploit reasoner: asked for a "step-by-step attack
        walkthrough", the model wrote real line breaks into the string. The
        JSON is otherwise complete, but strict parsing rejects control
        characters in strings and threw the whole answer away.
        """
        raw = ('[{"vuln_id": "VULN-006", "poc_description": "Steps:\n\n'
               '1. Find the endpoint\n2. Send the request"}]')
        parsed = orchestrator._parse_json(raw, "FB")
        assert parsed[0]["vuln_id"] == "VULN-006"
        assert "1. Find the endpoint" in parsed[0]["poc_description"]

    def test_literal_newlines_after_a_prose_preamble(self):
        """Both defects at once, which is what actually came back."""
        raw = ('Here is the analysis:\n\n[{"vuln_id": "VULN-006", '
               '"poc_description": "Step 1:\nsend a request"}]\n\n'
               'Note: exploitability is EASY.')
        assert orchestrator._parse_json(raw, "FB")[0]["vuln_id"] == "VULN-006"

    def test_still_falls_back_on_genuinely_broken_json(self):
        """Lenient parsing must not turn unparseable output into a false parse."""
        assert orchestrator._parse_json('[{"id": ', "FB") == "FB"

    def test_object_wins_over_an_array_nested_inside_it(self):
        """
        The report summary is an object whose second key is an array. The
        first balanced "[" span is found before the enclosing "{", so the
        whole summary used to be parsed down to just its recommendations.
        """
        raw = ('Here is the summary:\n\n{\n"executive_summary": "six findings",\n'
               '"key_recommendations": ["a", "b"]\n}')
        parsed = orchestrator._parse_json(raw, {"executive_summary": "fallback"})
        assert isinstance(parsed, dict)
        assert parsed["executive_summary"] == "six findings"

    def test_array_is_still_preferred_when_an_array_is_expected(self):
        raw = 'Findings:\n[{"id": "V1", "meta": {"a": 1}}]'
        parsed = orchestrator._parse_json(raw, [])
        assert isinstance(parsed, list)
        assert parsed[0]["id"] == "V1"

    def test_wrong_shape_still_beats_the_fallback(self):
        """A bare object where a list was expected: the caller can wrap it."""
        parsed = orchestrator._parse_json('{"vuln_id": "V1"}', [])
        assert parsed == {"vuln_id": "V1"}

    def test_array_wrapped_in_object(self):
        raw = '{"vulnerabilities": [{"id": "V4"}]}'
        assert orchestrator._parse_json(raw, "FB") == {"vulnerabilities": [{"id": "V4"}]}

    def test_brackets_inside_strings_do_not_confuse_the_scan(self):
        raw = 'Result: [{"description": "array [0] index ] here"}]'
        assert orchestrator._parse_json(raw, "FB") == [
            {"description": "array [0] index ] here"}
        ]

    def test_unparseable_returns_fallback(self):
        assert orchestrator._parse_json("I could not do that", "FB") == "FB"

    def test_empty_response_returns_fallback(self):
        assert orchestrator._parse_json("", "FB") == "FB"


# ── Severity normalisation ───────────────────────────────────────────────────

class TestSeverityNormalisation:
    @pytest.mark.parametrize("raw,expected", [
        ("ERROR", "HIGH"),
        ("WARNING", "MEDIUM"),
        ("INFO", "LOW"),
    ])
    def test_semgrep_levels_map_to_pipeline_levels(self, raw, expected):
        finding = {"source": "semgrep", "severity": raw}
        assert orchestrator._normalize_severity(finding) == expected

    @pytest.mark.parametrize("level", ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
    def test_bandit_levels_pass_through(self, level):
        finding = {"source": "bandit", "severity": level}
        assert orchestrator._normalize_severity(finding) == level

    def test_unknown_severity_defaults_to_medium(self):
        assert orchestrator._normalize_severity({"severity": "WEIRD"}) == "MEDIUM"

    def test_missing_severity_defaults_to_medium(self):
        assert orchestrator._normalize_severity({}) == "MEDIUM"


# ── Deterministic mapping ────────────────────────────────────────────────────

class TestDeterministicMapping:
    def test_sql_injection_maps_to_owasp_injection(self):
        raw = [{
            "source": "bandit",
            "file": "app/app.py",
            "line": 261,
            "severity": "MEDIUM",
            "description": "Possible SQL injection vector through string-based "
                           "query construction.",
            "test_id": "B608",
        }]
        vulns = orchestrator._vulns_from_raw_findings(raw)
        assert len(vulns) == 1
        assert vulns[0]["category"].startswith("A03:2021")
        assert vulns[0]["file"] == "app/app.py"
        assert vulns[0]["line"] == 261
        assert vulns[0]["rule"] == "B608"

    def test_every_finding_is_preserved(self):
        raw = [{"source": "bandit", "description": f"issue {i}"} for i in range(25)]
        assert len(orchestrator._vulns_from_raw_findings(raw)) == 25

    def test_ids_are_unique(self):
        raw = [{"source": "bandit", "description": f"issue {i}"} for i in range(5)]
        ids = [v["id"] for v in orchestrator._vulns_from_raw_findings(raw)]
        assert len(set(ids)) == len(ids)

    def test_existing_category_is_respected(self):
        raw = [{
            "source": "website",
            "category": "A02:2021-Cryptographic Failures",
            "description": "Missing security header",
            "severity": "HIGH",
        }]
        vulns = orchestrator._vulns_from_raw_findings(raw)
        assert vulns[0]["category"] == "A02:2021-Cryptographic Failures"


# ── The invariant ────────────────────────────────────────────────────────────

class TestFindingsSurviveLLMFailure:
    """The LLM must not be able to turn real findings into a clean report."""

    RAW = [
        {
            "source": "bandit",
            "file": "app/app.py",
            "line": 261,
            "severity": "MEDIUM",
            "description": "Possible SQL injection vector.",
            "test_id": "B608",
        },
        {
            "source": "bandit",
            "file": "app/app.py",
            "line": 329,
            "severity": "MEDIUM",
            "description": "Use of unsafe yaml load.",
            "test_id": "B506",
        },
    ]

    def _run(self, monkeypatch, llm_reply):
        class _Response:
            content = llm_reply

        monkeypatch.setattr(orchestrator, "invoke_llm", lambda *a, **k: _Response())
        state = {"raw_findings": self.RAW, "scan_id": "test"}
        return orchestrator.vuln_analyzer_node(state)

    def test_prose_only_reply_still_reports_findings(self, monkeypatch):
        """A markdown list with no JSON at all is unrecoverable by any parser."""
        result = self._run(
            monkeypatch,
            "Here are the findings:\n\n1. **Vulnerability 1**\n   * Source: bandit",
        )
        assert len(result["vulnerabilities"]) == len(self.RAW)

    def test_empty_array_reply_still_reports_findings(self, monkeypatch):
        result = self._run(monkeypatch, "[]")
        assert len(result["vulnerabilities"]) == len(self.RAW)

    def test_degraded_mode_is_disclosed_in_the_logs(self, monkeypatch):
        result = self._run(monkeypatch, "no idea")
        assert any("LLM enrichment unavailable" in line
                   for line in result["agent_logs"])

    def test_good_llm_output_enriches_without_shrinking_the_list(self, monkeypatch):
        """
        The model answered for one of the two findings. Its analysis is used,
        and the finding it skipped is still reported: its array is enrichment,
        not the result.
        """
        reply = ('[{"id": "VULN-001", "file": "app/app.py", "line": 261, '
                 '"severity": "CRITICAL", "category": "A03:2021-Injection", '
                 '"description": "SQL injection", "cve": null}]')
        result = self._run(monkeypatch, reply)
        vulns = result["vulnerabilities"]
        assert len(vulns) == len(self.RAW)
        assert vulns[0]["severity"] == "CRITICAL", "model severity is taken for source findings"
        assert vulns[0]["category"] == "A03:2021-Injection"
        assert vulns[1]["severity"] == "MEDIUM", "the skipped finding keeps the scanner's severity"
        assert not any("LLM enrichment unavailable" in line
                       for line in result["agent_logs"])
        assert any("missing from the model's output and were kept anyway" in line
                   for line in result["agent_logs"])

    def test_no_findings_stays_empty(self, monkeypatch):
        """A genuinely clean repo must still report clean."""
        class _Response:
            content = "[]"

        monkeypatch.setattr(orchestrator, "invoke_llm", lambda *a, **k: _Response())
        result = orchestrator.vuln_analyzer_node({"raw_findings": [], "scan_id": "t"})
        assert result["vulnerabilities"] == []


# ── Severity drift ───────────────────────────────────────────────────────────

class TestWebsiteSeverityIsNotTheModelsToChange:
    """
    Measured on a live scan: the scanner produced 6 website findings
    (2 MEDIUM, 4 LOW) and the analyzer returned 5 (3 MEDIUM, 2 LOW), dropping
    one finding and promoting another. The risk score is computed from this
    list, so the model was still moving the headline number after the score
    itself was made deterministic.

    Website findings come from header checks that are either true or not.
    """

    RAW = [
        {"source": "website", "file": "https://example.com/", "line": 0,
         "severity": "MEDIUM", "description": "Missing security header: X-Frame-Options"},
        {"source": "website", "file": "https://example.com/", "line": 0,
         "severity": "LOW", "description": "Missing security header: Permissions-Policy"},
        {"source": "website", "file": "https://example.com/", "line": 0,
         "severity": "LOW", "description": "Server information disclosed via 'server': GitHub.com"},
    ]

    def _run(self, monkeypatch, llm_reply):
        class _Response:
            content = llm_reply

        monkeypatch.setattr(orchestrator, "invoke_llm", lambda *a, **k: _Response())
        return orchestrator.vuln_analyzer_node({"raw_findings": self.RAW, "scan_id": "t"})

    # The drift as observed: one finding missing, one promoted LOW -> MEDIUM.
    DRIFTED = ('[{"id": "VULN-001", "severity": "MEDIUM", "category": "A05:2021-Security Misconfiguration",'
               ' "description": "Missing security header: X-Frame-Options", "cve": null},'
               ' {"id": "VULN-002", "severity": "MEDIUM", "category": "A05:2021-Security Misconfiguration",'
               ' "description": "Missing security header: Permissions-Policy", "cve": null}]')

    def test_no_finding_is_lost(self, monkeypatch):
        result = self._run(monkeypatch, self.DRIFTED)
        assert len(result["vulnerabilities"]) == len(self.RAW)

    def test_promotion_is_refused(self, monkeypatch):
        vulns = self._run(monkeypatch, self.DRIFTED)["vulnerabilities"]
        promoted = next(v for v in vulns if "Permissions-Policy" in v["description"])
        assert promoted["severity"] == "LOW"

    def test_severity_counts_match_the_scanner(self, monkeypatch):
        vulns = self._run(monkeypatch, self.DRIFTED)["vulnerabilities"]
        assert orchestrator.compute_risk(vulns)["counts"] == \
               orchestrator.compute_risk(self.RAW)["counts"]

    def test_the_score_is_unchanged_by_the_model(self, monkeypatch):
        """The whole point: the model cannot move the headline number."""
        vulns = self._run(monkeypatch, self.DRIFTED)["vulnerabilities"]
        assert orchestrator.compute_risk(vulns)["risk_score"] == \
               orchestrator.compute_risk(self.RAW)["risk_score"]

    def test_the_log_discloses_both_interventions(self, monkeypatch):
        logs = self._run(monkeypatch, self.DRIFTED)["agent_logs"]
        assert any("kept the scanner's severity" in line for line in logs)
        assert any("missing from the model's output" in line for line in logs)

    def test_careful_wording_is_not_rewritten(self, monkeypatch):
        """The meta-CSP and platform notes are deliberate; a rewrite loses them."""
        reply = ('[{"id": "VULN-001", "severity": "HIGH", '
                 '"description": "Implement X-Frame-Options to prevent clickjacking"}]')
        vulns = self._run(monkeypatch, reply)["vulnerabilities"]
        assert vulns[0]["description"] == "Missing security header: X-Frame-Options"

    def test_category_and_cve_are_still_taken_from_the_model(self, monkeypatch):
        """Enrichment the scanner genuinely cannot produce is still welcome."""
        reply = ('[{"id": "VULN-001", "severity": "HIGH", '
                 '"category": "A01:2021-Broken Access Control", "cve": "CVE-2021-1234"}]')
        vulns = self._run(monkeypatch, reply)["vulnerabilities"]
        assert vulns[0]["category"] == "A01:2021-Broken Access Control"
        assert vulns[0]["cve"] == "CVE-2021-1234"
        assert vulns[0]["severity"] == "MEDIUM"

    def test_short_form_ids_still_match(self, monkeypatch):
        """Observed on a repo scan: the model numbers VULN-1, the baseline VULN-001."""
        reply = ('[{"id": "VULN-2", "category": "A01:2021-Broken Access Control", '
                 '"description": "Missing security header: Permissions-Policy"}]')
        vulns = self._run(monkeypatch, reply)["vulnerabilities"]
        assert vulns[1]["category"] == "A01:2021-Broken Access Control"

    def test_a_vaguer_category_does_not_replace_the_owasp_label(self, monkeypatch):
        """The model answered "Security"; match_owasp_category() already did better."""
        reply = ('[{"id": "VULN-001", "category": "Security", '
                 '"description": "Missing security header: X-Frame-Options"}]')
        vulns = self._run(monkeypatch, reply)["vulnerabilities"]
        assert vulns[0]["category"] == "A05:2021-Security Misconfiguration"

    def test_spaced_owasp_labels_are_canonicalised(self, monkeypatch):
        """Otherwise the report lists A05:2021 twice, once with a trailing space."""
        reply = ('[{"id": "VULN-001", "category": "A05:2021 - Security Misconfiguration", '
                 '"description": "Missing security header: X-Frame-Options"}]')
        result = self._run(monkeypatch, reply)
        assert result["vulnerabilities"][0]["category"] == "A05:2021-Security Misconfiguration"
        cats = next(l for l in result["agent_logs"] if "OWASP categories" in l)
        assert cats.count("A05:2021") == 1

    def test_a_single_object_is_treated_as_a_one_item_array(self, monkeypatch):
        """
        A repo scan returned one bare object instead of an array, and the whole
        enrichment was discarded because only {"key": [...]} was unwrapped.
        """
        reply = ('{"id": "VULN-001", "category": "A03:2021-Injection", '
                 '"description": "Missing security header: X-Frame-Options"}')
        result = self._run(monkeypatch, reply)
        assert result["vulnerabilities"][0]["category"] == "A03:2021-Injection"
        assert not any("LLM enrichment unavailable" in line
                       for line in result["agent_logs"])

    def test_a_hallucinated_extra_finding_is_ignored(self, monkeypatch):
        reply = ('[{"id": "VULN-001", "severity": "MEDIUM", "description": "Missing security header: X-Frame-Options"},'
                 ' {"id": "VULN-099", "severity": "CRITICAL", "description": "Remote code execution in the login form"}]')
        vulns = self._run(monkeypatch, reply)["vulnerabilities"]
        assert len(vulns) == len(self.RAW)
        assert not any("Remote code execution" in v["description"] for v in vulns)


# ── Exploit reasoner ─────────────────────────────────────────────────────────

class TestExploitReasonerAccounting:
    """
    Same class of bug, one node later: the log counted the parsed LLM reply
    rather than the vulnerabilities it was given, so an unparseable reply
    printed "Analyzed 0 critical/high vulnerabilities" on a report that showed
    a HIGH finding and a generated patch for it.
    """

    VULNS = [
        {"id": "VULN-006", "file": "app/db.py", "line": 12, "severity": "HIGH",
         "category": "A03:2021-Injection", "description": "SQL injection", "cve": None},
        {"id": "VULN-007", "file": "app/auth.py", "line": 40, "severity": "MEDIUM",
         "category": "A01:2021-Broken Access Control", "description": "IDOR", "cve": None},
    ]

    def _run(self, monkeypatch, llm_reply):
        class _Response:
            content = llm_reply

        monkeypatch.setattr(orchestrator, "invoke_llm", lambda *a, **k: _Response())
        return orchestrator.exploit_reasoner_node(
            {"vulnerabilities": self.VULNS, "scan_id": "test"}
        )

    def test_unparseable_reply_still_accounts_for_every_target(self, monkeypatch):
        result = self._run(monkeypatch, "I could not analyse these.")
        assert [e["vuln_id"] for e in result["exploits"]] == ["VULN-006"]
        assert any("Analyzed 1/1" in line for line in result["agent_logs"])

    def test_fallback_entry_carries_real_owasp_context(self, monkeypatch):
        exploit = self._run(monkeypatch, "nonsense")["exploits"][0]
        assert exploit["exploitability"] == "UNKNOWN"
        assert "Injection" in exploit["attack_vector"]
        assert "app/db.py:12" in exploit["attack_vector"]
        assert exploit["source"] == "owasp-reference"

    def test_degraded_mode_is_disclosed_in_the_logs(self, monkeypatch):
        result = self._run(monkeypatch, "nonsense")
        assert any("LLM enrichment unavailable" in line
                   for line in result["agent_logs"])

    def test_good_llm_output_is_used_as_is(self, monkeypatch):
        reply = ('[{"vuln_id": "VULN-006", "exploitability": "EASY", '
                 '"attack_vector": "unauthenticated POST /login", '
                 '"impact": "database dump", "poc_description": "..."}]')
        result = self._run(monkeypatch, reply)
        assert result["exploits"][0]["exploitability"] == "EASY"
        assert not any("LLM enrichment unavailable" in line
                       for line in result["agent_logs"])

    def test_hallucinated_vuln_ids_are_dropped(self, monkeypatch):
        """An exploit for a finding that does not exist has nothing to link to."""
        reply = ('[{"vuln_id": "VULN-042", "exploitability": "EASY", '
                 '"attack_vector": "x", "impact": "y", "poc_description": "z"}]')
        result = self._run(monkeypatch, reply)
        assert [e["vuln_id"] for e in result["exploits"]] == ["VULN-006"]
        assert result["exploits"][0]["exploitability"] == "UNKNOWN"

    def test_medium_findings_are_not_reasoned_about(self, monkeypatch):
        """Only CRITICAL/HIGH are in scope, so VULN-007 must not appear."""
        result = self._run(monkeypatch, "nonsense")
        assert all(e["vuln_id"] != "VULN-007" for e in result["exploits"])
