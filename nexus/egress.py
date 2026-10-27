"""Runtime preflight: DNS pinning prerequisites, never opens a socket to the target."""
import ipaddress
import socket
from urllib.parse import urlsplit


def inspect_target(target_url: str, resolver=None) -> dict:
    """Validate all resolved addresses. This is NOT authorization to execute HTTP.

    DNS checks alone cannot prevent rebinding; the eventual transport must connect
    only to one of the validated IPs, preserving TLS hostname verification and SNI.
    """
    parsed = urlsplit(target_url)
    hostname = (parsed.hostname or '').rstrip('.').lower()
    if parsed.scheme != 'https' or parsed.port not in (None, 443) or parsed.username or parsed.password or not hostname:
        raise PermissionError('Only public HTTPS endpoints on port 443 are eligible')
    if hostname == 'localhost' or hostname.endswith(('.local', '.localhost', '.internal')):
        raise PermissionError('Local hostnames are blocked')
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        if '.' not in hostname:
            raise PermissionError('Unqualified hostnames are blocked')
    else:
        raise PermissionError('IP literals are blocked')
    resolver = resolver or socket.getaddrinfo
    try:
        records = resolver(hostname, 443, type=socket.SOCK_STREAM)
    except (OSError, ValueError) as exc:
        raise PermissionError('DNS resolution failed') from exc
    addresses = set()
    for record in records:
        address = record[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise PermissionError('Invalid DNS response') from exc
        if not ip.is_global:
            raise PermissionError('DNS response includes a non-public address')
        addresses.add(str(ip))
    if not addresses:
        raise PermissionError('DNS returned no usable addresses')
    return {'hostname': hostname, 'resolved_addresses': sorted(addresses),
            'safe_to_execute': False, 'requires_pinned_transport': True}
