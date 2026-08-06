"""
Which files a repository scan should not report findings against.

Test code is written to do unsafe things on purpose. A self-scan of this
project produced 231 findings, 218 of them in test files, and the fix suggester
dutifully proposed "fixing" the string "0.0.0.0" in test_url_guard.py — which is
the fixture that proves the URL guard blocks it. Applying that patch would break
the test it came from.

This is a real trade-off, not a free win: hardcoded credentials committed in a
test file are a genuine leak, and excluding tests hides them. The exclusion is
therefore counted and logged rather than silent, and SCAN_INCLUDE_TESTS=true
turns it off.
"""

from __future__ import annotations

import os

# Directory names that mean "this is test code", at any depth.
TEST_DIRECTORIES = frozenset({
    "test", "tests", "testing",
    "spec", "specs", "__tests__", "__mocks__",
    "e2e", "testdata", "fixtures", "mocks",
})

# Filenames that mean the same thing regardless of where they live.
_TEST_FILE_PREFIXES = ("test_",)
_TEST_FILE_SUFFIXES = ("_test.py", "_spec.py", ".test.js", ".test.ts", ".test.tsx",
                       ".spec.js", ".spec.ts", ".spec.tsx")
_TEST_FILENAMES = frozenset({"conftest.py"})


def include_tests() -> bool:
    """True when the caller has asked for test code to be scanned anyway."""
    return os.getenv("SCAN_INCLUDE_TESTS", "").strip().lower() in ("1", "true", "yes")


def is_test_path(path: str) -> bool:
    """True when a repo-relative path is test code rather than application code."""
    if not path:
        return False

    normalised = path.replace("\\", "/").strip("/")
    parts = normalised.split("/")
    if any(part.lower() in TEST_DIRECTORIES for part in parts[:-1]):
        return True

    filename = parts[-1].lower()
    if filename in _TEST_FILENAMES:
        return True
    if filename.startswith(_TEST_FILE_PREFIXES) and filename.endswith(".py"):
        return True
    return filename.endswith(_TEST_FILE_SUFFIXES)


def partition_test_findings(findings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split findings into (application code, test code)."""
    application, tests = [], []
    for finding in findings:
        (tests if is_test_path(finding.get("file", "")) else application).append(finding)
    return application, tests
