"""
Which hosts this installation is allowed to port scan.

Reading a website's headers is what every browser does. Connecting to 25 ports
on a host is not: it is the part of a scan that is unauthorised testing when the
host is not yours, and in several jurisdictions the part that is illegal. The
tool should not leave that to whoever is typing the URL, especially with a
scan box that accepts anything.

So the port scan is opt-in per host. HTTP checks always run; ports are probed
only against hosts the operator has declared they are authorised to test:

    AUTHORISED_SCAN_TARGETS=staging.example.com,*.internal.example.com

Matching is exact by default. A leading "*." authorises subdomains, and does
not authorise the apex on its own, so "*.example.com" covers api.example.com
but not example.com. Nothing is authorised by default.

Loopback and private addresses are treated as authorised when
ALLOW_PRIVATE_TARGETS is on, because that flag already means "I am testing my
own machine or network" and url_guard refuses those addresses otherwise.
"""

from __future__ import annotations

import ipaddress
import logging
import os

logger = logging.getLogger(__name__)

_ENV_VAR = "AUTHORISED_SCAN_TARGETS"


def authorised_patterns() -> list[str]:
    """The configured allowlist, normalised to lowercase."""
    raw = os.getenv(_ENV_VAR, "")
    return [p.strip().lower().rstrip(".") for p in raw.split(",") if p.strip()]


def _is_private_host(host: str) -> bool:
    if host in ("localhost", "localhost.localdomain"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local


def _matches(host: str, pattern: str) -> bool:
    if pattern.startswith("*."):
        suffix = pattern[1:]           # ".example.com"
        return host.endswith(suffix) and host != suffix.lstrip(".")
    return host == pattern


def is_authorised(host: str) -> bool:
    """True when this host may be port scanned."""
    hostname = (host or "").strip().lower().rstrip(".")
    if not hostname:
        return False

    if _is_private_host(hostname):
        # url_guard already blocks these unless the operator opted in, and that
        # opt-in is the same assertion this function is asking about.
        return os.getenv("ALLOW_PRIVATE_TARGETS", "").strip().lower() in ("1", "true", "yes")

    return any(_matches(hostname, pattern) for pattern in authorised_patterns())


def refusal_reason(host: str) -> str:
    """Why the port scan was skipped, in terms the operator can act on."""
    configured = authorised_patterns()
    if not configured:
        return (
            f"{host} is not an authorised scan target. Port scanning a host you "
            f"do not control is unauthorised testing, so it is off by default. "
            f"Set {_ENV_VAR} to the hosts you are authorised to test. HTTP "
            f"checks were still performed."
        )
    return (
        f"{host} is not in {_ENV_VAR} ({', '.join(configured)}), so its ports "
        f"were not probed. HTTP checks were still performed."
    )
