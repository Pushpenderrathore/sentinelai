"""
Target URL validation — blocks SSRF against internal infrastructure.

Every scan target is resolved and checked before any request is made.
Private, loopback, link-local, and cloud-metadata addresses are rejected
unless ALLOW_PRIVATE_TARGETS=true (useful for local demos / lab testing).
"""

from __future__ import annotations

import ipaddress
import os
import socket
import urllib.parse


class UnsafeTargetError(ValueError):
    """Raised when a scan target resolves to a non-public address."""


def _allow_private() -> bool:
    return os.getenv("ALLOW_PRIVATE_TARGETS", "false").lower() in ("1", "true", "yes")


def _is_public_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def assert_safe_target(url: str) -> str:
    """
    Validate a scan target URL. Returns the normalised URL or raises
    UnsafeTargetError / ValueError with a user-presentable message.
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")
    if parsed.port and parsed.port not in (80, 443, 8080, 8443):
        raise UnsafeTargetError("Only standard web ports (80, 443, 8080, 8443) may be targeted")

    if _allow_private():
        return url

    try:
        infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve hostname '{hostname}'") from exc

    for info in infos:
        ip = info[4][0]
        if not _is_public_ip(ip):
            raise UnsafeTargetError(
                f"Target '{hostname}' resolves to a private/internal address — scanning "
                f"internal infrastructure is blocked. Set ALLOW_PRIVATE_TARGETS=true to "
                f"override for lab use."
            )

    return url
