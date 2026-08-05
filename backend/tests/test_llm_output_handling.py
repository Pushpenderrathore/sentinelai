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

    def test_good_llm_output_is_used_as_is(self, monkeypatch):
        reply = ('[{"id": "VULN-001", "file": "app/app.py", "line": 261, '
                 '"severity": "CRITICAL", "category": "A03:2021-Injection", '
                 '"description": "SQL injection", "cve": null}]')
        result = self._run(monkeypatch, reply)
        assert len(result["vulnerabilities"]) == 1
        assert result["vulnerabilities"][0]["severity"] == "CRITICAL"
        assert not any("LLM enrichment unavailable" in line
                       for line in result["agent_logs"])

    def test_no_findings_stays_empty(self, monkeypatch):
        """A genuinely clean repo must still report clean."""
        class _Response:
            content = "[]"

        monkeypatch.setattr(orchestrator, "invoke_llm", lambda *a, **k: _Response())
        result = orchestrator.vuln_analyzer_node({"raw_findings": [], "scan_id": "t"})
        assert result["vulnerabilities"] == []
