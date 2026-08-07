"""
Tests for grading an open port in context.

Scanning a locally-running OWASP Juice Shop found the *host machine's* services
rather than the container's, and reported the developer's loopback PostgreSQL
as "exposed to internet - direct database access possible". That is false: the
service is bound to loopback and unreachable from anywhere else. It also took
the demo scan to 100/100 CRITICAL on the strength of it.
"""

from __future__ import annotations

import pytest

from agents.orchestrator import compute_risk
from tools import port_scanner


@pytest.fixture
def fake_open_ports(monkeypatch):
    """Report 5432 and 8080 as open, whatever host is scanned."""
    def _probe(ip, port):
        return port, port in (5432, 8080), ""
    monkeypatch.setattr(port_scanner, "_probe_port", _probe)


class TestLoopbackIsNotTheInternet:
    @pytest.fixture(autouse=True)
    def _resolve_to_loopback(self, monkeypatch):
        monkeypatch.setattr(port_scanner.socket, "gethostbyname", lambda h: "127.0.0.1")

    def test_postgres_on_loopback_is_not_critical(self, fake_open_ports):
        pg = next(p for p in port_scanner.scan_ports("localhost") if p.get("port") == 5432)
        assert pg["severity"] == "MEDIUM", "CRITICAL implies reachable from outside"

    def test_the_wording_does_not_claim_internet_exposure(self, fake_open_ports):
        for finding in port_scanner.scan_ports("localhost"):
            if "port" not in finding:
                continue
            assert "exposed to internet" not in finding["description"]
            assert "loopback" in finding["description"]

    def test_it_says_whose_machine_this_is(self, fake_open_ports):
        pg = next(p for p in port_scanner.scan_ports("localhost") if p.get("port") == 5432)
        assert "the host running the scan" in pg["description"]

    def test_the_recommendation_is_not_a_false_alarm(self, fake_open_ports):
        pg = next(p for p in port_scanner.scan_ports("localhost") if p.get("port") == 5432)
        assert "Nothing to fix" in pg["recommendation"]

    def test_findings_are_marked_as_loopback(self, fake_open_ports):
        assert all(p["loopback"] is True
                   for p in port_scanner.scan_ports("localhost") if "port" in p)

    def test_a_local_scan_does_not_reach_100(self, fake_open_ports):
        """The demo scan hit 100/100 CRITICAL on the strength of a local database."""
        findings = [p for p in port_scanner.scan_ports("localhost") if "port" in p]
        assert compute_risk(findings)["risk_score"] < 80


class TestRemoteHostsAreUnchanged:
    @pytest.fixture(autouse=True)
    def _resolve_to_public(self, monkeypatch):
        monkeypatch.setattr(port_scanner.socket, "gethostbyname", lambda h: "203.0.113.10")

    def test_postgres_on_a_public_host_is_still_critical(self, fake_open_ports):
        pg = next(p for p in port_scanner.scan_ports("db.example.com") if p.get("port") == 5432)
        assert pg["severity"] == "CRITICAL"
        assert "exposed to internet" in pg["description"]

    def test_not_marked_as_loopback(self, fake_open_ports):
        assert all(p["loopback"] is False
                   for p in port_scanner.scan_ports("db.example.com") if "port" in p)
