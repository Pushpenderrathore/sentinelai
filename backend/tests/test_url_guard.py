"""
Tests for the scan-target guard.

This is the control that stops the scanner being pointed at internal
infrastructure (SSRF). It is security-critical, so the negative cases matter
more than the positive ones.

DNS is stubbed throughout so the suite never depends on the network.
"""

from __future__ import annotations

import pytest

from tools import url_guard
from tools.url_guard import UnsafeTargetError


def _stub_dns(monkeypatch, ip: str):
    monkeypatch.setattr(
        url_guard.socket, "getaddrinfo",
        lambda *a, **k: [(None, None, None, None, (ip, 0))],
    )


@pytest.fixture(autouse=True)
def deny_private_by_default(monkeypatch):
    monkeypatch.setenv("ALLOW_PRIVATE_TARGETS", "false")
    yield


class TestBlocksInternalTargets:
    @pytest.mark.parametrize("ip", [
        "127.0.0.1",        # loopback
        "10.0.0.5",         # RFC 1918
        "192.168.1.10",     # RFC 1918
        "172.16.0.1",       # RFC 1918
        "169.254.169.254",  # cloud metadata
        "0.0.0.0",          # unspecified
    ])
    def test_private_addresses_are_rejected(self, monkeypatch, ip):
        _stub_dns(monkeypatch, ip)
        with pytest.raises(UnsafeTargetError):
            url_guard.assert_safe_target("http://internal.example")

    def test_ipv6_loopback_is_rejected(self, monkeypatch):
        _stub_dns(monkeypatch, "::1")
        with pytest.raises(UnsafeTargetError):
            url_guard.assert_safe_target("http://internal.example")

    def test_ipv4_mapped_ipv6_is_judged_on_the_embedded_address(self, monkeypatch):
        """::ffff:127.0.0.1 must not slip past as an IPv6 address."""
        _stub_dns(monkeypatch, "::ffff:127.0.0.1")
        with pytest.raises(UnsafeTargetError):
            url_guard.assert_safe_target("http://internal.example")


class TestAllowsPublicTargets:
    def test_public_address_passes(self, monkeypatch):
        _stub_dns(monkeypatch, "93.184.216.34")
        assert url_guard.assert_safe_target("https://example.com") == "https://example.com"

    def test_scheme_is_added_when_missing(self, monkeypatch):
        _stub_dns(monkeypatch, "93.184.216.34")
        assert url_guard.assert_safe_target("example.com").startswith("https://")


class TestPortAllowlist:
    @pytest.mark.parametrize("port", [80, 443, 8080, 8443])
    def test_web_ports_allowed(self, monkeypatch, port):
        _stub_dns(monkeypatch, "93.184.216.34")
        url_guard.assert_safe_target(f"http://example.com:{port}")

    @pytest.mark.parametrize("port", [22, 3306, 6379, 9200])
    def test_non_web_ports_rejected(self, monkeypatch, port):
        _stub_dns(monkeypatch, "93.184.216.34")
        with pytest.raises(UnsafeTargetError):
            url_guard.assert_safe_target(f"http://example.com:{port}")


class TestLabOverride:
    def test_private_allowed_when_explicitly_enabled(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_TARGETS", "true")
        assert url_guard.assert_safe_target("http://localhost:8080")

    def test_override_does_not_bypass_the_port_allowlist(self, monkeypatch):
        monkeypatch.setenv("ALLOW_PRIVATE_TARGETS", "true")
        with pytest.raises(UnsafeTargetError):
            url_guard.assert_safe_target("http://localhost:22")


class TestMalformedInput:
    def test_url_without_hostname_is_rejected(self):
        with pytest.raises(ValueError):
            url_guard.assert_safe_target("http://")

    def test_unresolvable_hostname_is_rejected(self, monkeypatch):
        def _boom(*_a, **_k):
            raise url_guard.socket.gaierror("no such host")

        monkeypatch.setattr(url_guard.socket, "getaddrinfo", _boom)
        with pytest.raises(ValueError):
            url_guard.assert_safe_target("https://nonexistent.invalid")
