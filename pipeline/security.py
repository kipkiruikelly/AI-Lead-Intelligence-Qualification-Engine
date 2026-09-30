"""
pipeline/security.py
────────────────────
URL validation and SSRF (Server-Side Request Forgery) protection.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse


def is_safe_url(url: str) -> bool:
    """
    Check if a URL is safe to fetch (prevents SSRF attacks to internal/private networks).
    Blocks localhost, 127.0.0.1, 169.254.169.254, 10.x.x.x, 172.16-31.x.x, 192.168.x.x, and loopbacks.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return False

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False

        hostname = hostname.lower()

        # Block localhost / loopback names
        if hostname in ("localhost", "localhost.localdomain", "broadcasthost", "local"):
            return False

        # Resolve IP address
        try:
            ip_str = socket.gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip_str)

            # Check if IP is private, loopback, link-local, or reserved
            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_link_local
                or ip_obj.is_reserved
                or ip_obj.is_multicast
            ):
                return False
        except socket.gaierror:
            # Domain failed resolution
            return False

        return True
    except Exception:
        return False
