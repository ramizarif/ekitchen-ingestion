"""URL validation and SSRF protection."""
import ipaddress
import socket
from urllib.parse import urlparse

BLOCKED_HOSTS = {
    'localhost', '127.0.0.1', '0.0.0.0', '::1',
    'metadata.google.internal',
    'instance-data',
}

BLOCKED_SUFFIXES = [
    '.railway.internal',
    '.local',
    '.internal',
]


def is_safe_url(url: str) -> tuple[bool, str]:
    """
    Validate URL is safe for server-side requests (SSRF prevention).
    Returns (is_safe, reason).
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    if parsed.scheme not in ('http', 'https'):
        return False, f"Unsupported scheme: {parsed.scheme}"

    if not parsed.netloc:
        return False, "Missing host"

    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname"

    if hostname in BLOCKED_HOSTS:
        return False, f"Blocked host: {hostname}"

    for suffix in BLOCKED_SUFFIXES:
        if hostname.endswith(suffix):
            return False, f"Internal domain blocked: {hostname}"

    try:
        resolved_ips = socket.getaddrinfo(hostname, None)
        for _, _, _, _, addr in resolved_ips:
            ip = ipaddress.ip_address(addr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False, f"Resolved to private/reserved IP: {ip}"
            if addr[0] == '169.254.169.254':
                return False, "Cloud metadata endpoint blocked"
    except socket.gaierror:
        return False, f"DNS resolution failed: {hostname}"

    return True, "OK"
