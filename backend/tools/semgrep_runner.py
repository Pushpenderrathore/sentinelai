"""Runs Semgrep with the auto ruleset and returns normalized findings."""

from __future__ import annotations

import json
import os
import shutil
import subprocess  # nosec B404 - argument list only, never shell=True
import sys


def _semgrep_bin() -> str:
    """
    Absolute path to semgrep: the venv copy if there is one, else whatever is on
    PATH. Resolved rather than invoked by bare name, so an executable planted
    earlier on PATH cannot take its place.
    """
    venv_bin = os.path.join(os.path.dirname(sys.executable), "semgrep")
    if os.path.isfile(venv_bin):
        return venv_bin
    resolved = shutil.which("semgrep")
    if not resolved:
        raise RuntimeError("semgrep is not installed or not on PATH")
    return resolved


def _relative(path: str, repo_path: str) -> str:
    """Report paths relative to the repo root. Repos are cloned into a temp
    directory, so the absolute path leaks a meaningless location into reports."""
    if not path:
        return path
    try:
        return os.path.relpath(path, repo_path)
    except ValueError:
        return path


def _semgrep_config() -> str:
    """
    Ruleset to scan with.

    "auto" resolves rules from the Semgrep registry over the network, so with no
    internet it silently produces zero findings. Point SEMGREP_RULES_PATH at a
    local checkout of semgrep-rules (or any directory of rule YAML) to scan
    fully offline:

        git clone --depth 1 https://github.com/semgrep/semgrep-rules ~/.semgrep-rules
        SEMGREP_RULES_PATH=~/.semgrep-rules
    """
    local = os.getenv("SEMGREP_RULES_PATH", "").strip()
    if local:
        expanded = os.path.expanduser(local)
        if os.path.isdir(expanded):
            return expanded
    return "auto"


def run_semgrep(repo_path: str) -> list[dict]:
    # nosec B603 - resolved executable, fixed argument list, no shell.
    result = subprocess.run(  # nosec B603
        [_semgrep_bin(), "--config", _semgrep_config(), repo_path,
         "--json", "--quiet"],
        capture_output=True,
        text=True,
        timeout=180,
    )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    normalized = []
    for finding in data.get("results", []):
        extra = finding.get("extra", {})
        normalized.append({
            "source": "semgrep",
            "file": _relative(finding.get("path", ""), repo_path),
            "line": finding.get("start", {}).get("line", 0),
            "severity": extra.get("severity", "WARNING").upper(),
            "description": extra.get("message", ""),
            "code": extra.get("lines", ""),
            "rule_id": finding.get("check_id", ""),
        })

    return normalized
