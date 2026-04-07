"""URL normalisation for caching and idempotency keys."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit


def canonical_url(raw: str) -> str:
    """Return a canonical URL string for stable cache keys.

    Normalisations:
    - strip whitespace
    - lower-case scheme and host
    - remove default ports (80/443)
    - drop fragments
    - ensure path is at least "/"
    """
    s = (raw or "").strip()
    if not s:
        return ""
    parts = urlsplit(s)
    scheme = (parts.scheme or "").lower()
    netloc = parts.netloc
    if not scheme and netloc:
        scheme = "https"

    host = (parts.hostname or "").lower()
    port = parts.port
    userinfo = ""
    if parts.username:
        userinfo = parts.username
        if parts.password:
            userinfo += f":{parts.password}"
        userinfo += "@"

    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    port_s = "" if port is None or default_port else f":{port}"
    netloc = f"{userinfo}{host}{port_s}" if host else parts.netloc

    path = parts.path or "/"
    return urlunsplit((scheme or parts.scheme, netloc, path, parts.query, ""))

