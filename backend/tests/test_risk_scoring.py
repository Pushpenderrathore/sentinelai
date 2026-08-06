"""
Regression tests for the risk score.

The score used to be whatever integer the report-writing model produced, and it
did not survive comparison between two scans: a site with 12 findings
(1 HIGH, 5 MEDIUM, 6 LOW) scored 20/100 LOW, while one with 6 findings
(1 HIGH, 2 MEDIUM, 3 LOW) scored 40/100 MEDIUM. Half the findings, less severe,
double the score.

It is the largest number in the UI, it is plotted as a trend across rescans of
the same site, and anyone can rescan and check it. These tests protect the
three properties that makes possible: it is reproducible, it is monotonic in
the findings, and the model cannot overwrite it.
"""

from __future__ import annotations

from agents import orchestrator
from agents.orchestrator import compute_risk


def _vulns(**counts: int) -> list[dict]:
    """_vulns(HIGH=1, LOW=2) -> one HIGH and two LOW vulnerabilities."""
    return [
        {"id": f"VULN-{i:03d}", "severity": sev, "file": "https://example.com/",
         "category": "A05:2021-Security Misconfiguration",
         "description": f"Finding {i} ({sev})"}
        for i, sev in enumerate(
            [sev for sev, n in counts.items() for _ in range(n)], start=1
        )
    ]


# ── The incident ─────────────────────────────────────────────────────────────

class TestScoresAreComparableAcrossScans:
    LINKEDIN = _vulns(HIGH=1, MEDIUM=5, LOW=6)    # scored 20/100 LOW
    PORTFOLIO = _vulns(HIGH=1, MEDIUM=2, LOW=3)   # scored 40/100 MEDIUM

    def test_more_and_worse_findings_score_higher(self):
        assert (compute_risk(self.LINKEDIN)["risk_score"]
                > compute_risk(self.PORTFOLIO)["risk_score"])

    def test_same_findings_always_score_the_same(self):
        first = compute_risk(self.LINKEDIN)
        second = compute_risk(list(reversed(self.LINKEDIN)))
        assert first["risk_score"] == second["risk_score"]
        assert first["overall_risk"] == second["overall_risk"]

    def test_fixing_a_finding_lowers_the_score(self):
        """The demo loop: scan, fix, rescan, show the number fall."""
        before = compute_risk(self.PORTFOLIO)["risk_score"]
        after = compute_risk(_vulns(MEDIUM=2, LOW=3))["risk_score"]
        assert after < before


# ── Monotonicity ─────────────────────────────────────────────────────────────

class TestMonotonic:
    def test_adding_a_finding_never_lowers_the_score(self):
        base = compute_risk(_vulns(MEDIUM=2))["risk_score"]
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            added = {"MEDIUM": 2}
            added[sev] = added.get(sev, 0) + 1
            worse = compute_risk(_vulns(**added))["risk_score"]
            assert worse >= base, sev

    def test_severity_ordering_holds_for_a_single_finding(self):
        scores = [compute_risk(_vulns(**{sev: 1}))["risk_score"]
                  for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW")]
        assert scores == sorted(scores, reverse=True)


# ── Boundaries ───────────────────────────────────────────────────────────────

class TestBounds:
    def test_clean_scan_scores_zero(self):
        risk = compute_risk([])
        assert risk["risk_score"] == 0
        assert risk["overall_risk"] == "LOW"

    def test_score_is_capped_at_100(self):
        assert compute_risk(_vulns(CRITICAL=50))["risk_score"] == 100

    def test_a_pile_of_low_findings_is_not_a_crisis(self):
        """Band caps: 40 informational findings must not read as CRITICAL."""
        risk = compute_risk(_vulns(LOW=40))
        assert risk["overall_risk"] == "LOW"
        assert risk["risk_score"] <= 10

    def test_a_single_critical_is_not_diluted_into_a_low_score(self):
        """Floors: one RCE in an otherwise clean repo is a CRITICAL-risk repo."""
        risk = compute_risk(_vulns(CRITICAL=1))
        assert risk["risk_score"] >= 80
        assert risk["overall_risk"] == "CRITICAL"

    def test_unknown_severity_is_treated_as_medium(self):
        """Matches _normalize_severity, so a stray label cannot score zero."""
        risk = compute_risk([{"id": "VULN-001", "severity": "IMPORTANT"}])
        assert risk["counts"]["MEDIUM"] == 1

    def test_missing_severity_key_does_not_crash(self):
        assert compute_risk([{"id": "VULN-001"}])["risk_score"] > 0


# ── Auditability ─────────────────────────────────────────────────────────────

class TestBreakdownIsShown:
    def test_breakdown_explains_the_number(self):
        risk = compute_risk(_vulns(HIGH=1, MEDIUM=5, LOW=6))
        assert risk["counts"] == {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 5, "LOW": 6}
        assert sum(risk["contributions"].values()) >= risk["risk_score"] or risk["floor_applied"]


# ── The model no longer owns the number ──────────────────────────────────────

class TestReportGeneratorIgnoresModelScore:
    VULNS = _vulns(HIGH=1, MEDIUM=2, LOW=3)

    def _report(self, monkeypatch, llm_reply):
        class _Response:
            content = llm_reply

        monkeypatch.setattr(orchestrator, "invoke_llm", lambda *a, **k: _Response())
        return orchestrator.report_generator_node(
            {"scan_id": "test", "repo_url": "https://example.com",
             "vulnerabilities": self.VULNS}
        )["report"]

    def test_model_supplied_score_is_overwritten(self, monkeypatch):
        """The old failure mode: the model claimed 20/100 LOW for these."""
        expected = compute_risk(self.VULNS)
        report = self._report(
            monkeypatch,
            '{"executive_summary": "ok", "risk_score": 3, '
            '"overall_risk": "LOW", "key_recommendations": ["a"]}',
        )
        assert report["summary"]["risk_score"] == expected["risk_score"]
        assert report["summary"]["overall_risk"] == expected["overall_risk"]

    def test_unparseable_reply_still_scores_the_findings(self, monkeypatch):
        """Falling back to a hardcoded 50/100 MEDIUM would be a made-up number."""
        report = self._report(monkeypatch, "I cannot help with that.")
        assert report["summary"]["risk_score"] == compute_risk(self.VULNS)["risk_score"]

    def test_report_carries_the_arithmetic(self, monkeypatch):
        breakdown = self._report(monkeypatch, "nope")["summary"]["risk_breakdown"]
        assert breakdown["counts"]["HIGH"] == 1
        assert "method" in breakdown

    def test_recommendations_fall_back_to_the_findings(self, monkeypatch):
        """An empty recommendations section under six findings reads as "all clear"."""
        report = self._report(monkeypatch, '{"executive_summary": "ok"}')
        recs = report["summary"]["key_recommendations"]
        assert len(recs) == 3
        assert all(isinstance(r, str) for r in recs)
        assert recs[0].startswith("[HIGH]"), "most severe finding must lead"

    def test_model_recommendations_are_kept_when_present(self, monkeypatch):
        report = self._report(
            monkeypatch,
            '{"executive_summary": "ok", "key_recommendations": ["Rotate the keys"]}',
        )
        assert report["summary"]["key_recommendations"] == ["Rotate the keys"]

    def test_clean_scan_gets_no_invented_recommendations(self, monkeypatch):
        class _Response:
            content = '{"executive_summary": "clean"}'

        monkeypatch.setattr(orchestrator, "invoke_llm", lambda *a, **k: _Response())
        report = orchestrator.report_generator_node(
            {"scan_id": "t", "repo_url": "https://example.com", "vulnerabilities": []}
        )["report"]
        assert report["summary"]["key_recommendations"] == []

    def test_logs_state_the_score_is_calculated(self, monkeypatch):
        class _Response:
            content = "nope"

        monkeypatch.setattr(orchestrator, "invoke_llm", lambda *a, **k: _Response())
        result = orchestrator.report_generator_node(
            {"scan_id": "test", "repo_url": "https://example.com",
             "vulnerabilities": self.VULNS}
        )
        assert any("not model-generated" in line for line in result["agent_logs"])
