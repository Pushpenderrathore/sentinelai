"""
Tests for excluding test code from repository scan results.

A self-scan of this project produced 231 findings, 218 of them in test files.
One generated patch proposed replacing "0.0.0.0" in test_url_guard.py with
"127.0.0.1" — that string is the fixture proving the URL guard blocks 0.0.0.0,
so applying the patch would break the test that motivated it.
"""

from __future__ import annotations

import pytest

from agents import orchestrator
from tools import scan_exclusions
from tools.scan_exclusions import is_test_path, partition_test_findings


class TestIsTestPath:
    @pytest.mark.parametrize("path", [
        "backend/tests/test_url_guard.py",
        "tests/conftest.py",
        "backend/tests/helpers/data.py",
        "frontend/__tests__/ws.ts",
        "src/spec/login_spec.py",
        "e2e/checkout.py",
        "app/testdata/sample.py",
        "frontend/lib/ws.test.ts",
        "frontend/components/Button.spec.tsx",
        "backend/agents/orchestrator_test.py",
        "test_thing.py",
    ])
    def test_test_code_is_recognised(self, path):
        assert is_test_path(path) is True

    @pytest.mark.parametrize("path", [
        "backend/agents/orchestrator.py",
        "frontend/lib/ws.ts",
        ".github/workflows/ci.yml",
        "backend/tools/website_scanner.py",
        "src/latest/index.js",
        "app/contest/views.py",
        "",
    ])
    def test_application_code_is_not(self, path):
        assert is_test_path(path) is False

    def test_windows_separators(self):
        assert is_test_path("backend\\tests\\test_x.py") is True

    def test_a_directory_named_test_only_counts_as_a_directory(self):
        """"test.py" in the app is application code; the parent dirs decide."""
        assert is_test_path("backend/test.py") is False

    def test_case_insensitive_directories(self):
        assert is_test_path("backend/Tests/thing.py") is True


class TestPartition:
    FINDINGS = [
        {"file": "backend/agents/orchestrator.py", "severity": "HIGH"},
        {"file": "backend/tests/test_url_guard.py", "severity": "LOW"},
        {"file": "frontend/lib/ws.ts", "severity": "MEDIUM"},
        {"file": "frontend/lib/ws.test.ts", "severity": "LOW"},
    ]

    def test_splits_both_ways(self):
        app, tests = partition_test_findings(self.FINDINGS)
        assert [f["file"] for f in app] == [
            "backend/agents/orchestrator.py", "frontend/lib/ws.ts"]
        assert len(tests) == 2

    def test_nothing_is_lost(self):
        app, tests = partition_test_findings(self.FINDINGS)
        assert len(app) + len(tests) == len(self.FINDINGS)

    def test_findings_without_a_file_are_kept(self):
        app, tests = partition_test_findings([{"severity": "HIGH"}])
        assert len(app) == 1


class TestIncludeTestsOverride:
    def test_off_by_default(self, monkeypatch):
        monkeypatch.delenv("SCAN_INCLUDE_TESTS", raising=False)
        assert scan_exclusions.include_tests() is False

    @pytest.mark.parametrize("value", ["true", "TRUE", "1", "yes"])
    def test_can_be_turned_on(self, monkeypatch, value):
        monkeypatch.setenv("SCAN_INCLUDE_TESTS", value)
        assert scan_exclusions.include_tests() is True

    def test_other_values_do_not_enable_it(self, monkeypatch):
        monkeypatch.setenv("SCAN_INCLUDE_TESTS", "no")
        assert scan_exclusions.include_tests() is False


class TestScannerAppliesTheExclusion:
    """The scanner node reports the exclusion rather than performing it silently."""

    def _scan(self, monkeypatch, tmp_path):
        monkeypatch.setattr(orchestrator, "invoke_llm", None, raising=False)

        import tools.git_cloner as git_cloner
        import tools.bandit_runner as bandit_runner
        import tools.semgrep_runner as semgrep_runner

        monkeypatch.setattr(git_cloner, "clone_repo", lambda *a: str(tmp_path))
        monkeypatch.setattr(git_cloner, "detect_tech_stack",
                            lambda p: {"languages": ["python"]})
        monkeypatch.setattr(bandit_runner, "run_bandit", lambda p: [
            {"source": "bandit", "file": "backend/agents/orchestrator.py",
             "line": 1, "severity": "MEDIUM", "description": "real"},
            {"source": "bandit", "file": "backend/tests/test_url_guard.py",
             "line": 2, "severity": "LOW", "description": "fixture"},
        ])
        monkeypatch.setattr(semgrep_runner, "run_semgrep", lambda p: [])
        return orchestrator._scan_github({"repo_url": "https://github.com/a/b",
                                          "scan_id": "t"})

    def test_test_findings_are_dropped(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SCAN_INCLUDE_TESTS", raising=False)
        result = self._scan(monkeypatch, tmp_path)
        files = [f["file"] for f in result["raw_findings"]]
        assert files == ["backend/agents/orchestrator.py"]

    def test_the_exclusion_is_logged_with_a_count(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SCAN_INCLUDE_TESTS", raising=False)
        result = self._scan(monkeypatch, tmp_path)
        assert any("Excluded 1 findings in test files" in line
                   for line in result["agent_logs"])

    def test_the_override_keeps_them(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SCAN_INCLUDE_TESTS", "true")
        result = self._scan(monkeypatch, tmp_path)
        assert len(result["raw_findings"]) == 2
        assert any("Scanning test code as well" in line
                   for line in result["agent_logs"])
