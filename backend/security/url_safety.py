"""URL safety helpers (SSRF protection).

This project crawls user-provided URLs. That is high-risk for SSRF because a
malicious user can attempt to crawl localhost, private RFC1918 ranges, or cloud
metadata IPs. These helpers enforce a "public internet only" policy.
"""

from __future__ import annotations

import os
import socket
from ipaddress import ip_address
from urllib.parse import urlparse

def _env_flag(name: str) -> bool:
    v = (os.environ.get(name) or "").strip().lower()
    return v in {"1", "true", "yes", "y", "on"}


def _is_ip_blocked(ip: str) -> bool:
    try:
        addr = ip_address(ip)
    except ValueError:
        return False
    return bool(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def validate_public_url(url: str) -> tuple[bool, str]:
    """Validate a URL is safe to crawl from this server.

    Returns (ok, reason). If ok is True, reason is "".

    ALLOW_PRIVATE_URLS can be enabled for controlled environments to bypass SSRF protections.
    """

    if _env_flag("ALLOW_PRIVATE_URLS"):
        return True, ""

    raw = (url or "").strip()
    if not raw:
        return False, "URL is empty"

    p = urlparse(raw)
    if p.scheme not in ("http", "https"):
        return False, "URL must start with http:// or https://"
    if not p.netloc:
        return False, "URL must include a hostname"

    # Block userinfo tricks: http://127.0.0.1@evil.com/
    if p.username or p.password:
        return False, "URL must not include username/password"

    host = p.hostname
    if not host:
        return False, "URL hostname could not be parsed"

    h = host.strip().lower().rstrip(".")
    if h in {"localhost", "localhost.localdomain"} or h.endswith(".localhost"):
        return False, "Localhost addresses are not allowed"

    # If user supplied a literal IP address, block private/link-local/etc.
    if _is_ip_blocked(h):
        return False, "Private or special-purpose IPs are not allowed"

    # Resolve DNS and ensure *all* A/AAAA records are public.
    # This prevents: http://attacker.com -> 127.0.0.1
    try:
        infos = socket.getaddrinfo(h, p.port or (443 if p.scheme == "https" else 80))
    except socket.gaierror:
        return False, "Hostname could not be resolved"
    except Exception as e:  # noqa: BLE001
        return False, f"Hostname resolution failed: {e!s}"

    resolved: set[str] = set()
    for family, _, _, _, sockaddr in infos:
        if family == socket.AF_INET:
            resolved.add(sockaddr[0])
        elif family == socket.AF_INET6:
            resolved.add(sockaddr[0])

    if not resolved:
        return False, "Hostname did not resolve to an IP address"

    blocked = [ip for ip in sorted(resolved) if _is_ip_blocked(ip)]
    if blocked:
        return False, f"Hostname resolves to blocked IP(s): {', '.join(blocked)}"

    return True, ""

