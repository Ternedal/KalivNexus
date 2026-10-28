"""Opt-in bounded, DNS-pinned GET executor. Never follows redirects."""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit

from nexus.egress import inspect_target

MAX_BYTES = 262_144
TOTAL_DEADLINE_SECONDS = 8.0


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname, pinned_ip, timeout=5):
        super().__init__(hostname, 443, timeout=timeout, context=ssl.create_default_context())
        self.pinned_ip = pinned_ip

    def connect(self):
        # TLS verification and SNI continue to use the original hostname.
        sock = socket.create_connection((self.pinned_ip, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def execute_get(url: str, *, resolver=None, connection_factory=PinnedHTTPSConnection, deadline_seconds=TOTAL_DEADLINE_SECONDS, clock=time.monotonic):
    """Return bounded response metadata and UTF-8 text; caller must authorize first."""
    if not 0 < deadline_seconds <= TOTAL_DEADLINE_SECONDS:
        raise ValueError("Invalid execution deadline")
    deadline = clock() + deadline_seconds

    def remaining():
        budget = deadline - clock()
        if budget <= 0:
            raise TimeoutError("Execution deadline exceeded")
        return budget

    preflight = inspect_target(url, resolver=resolver)
    remaining()
    parsed = urlsplit(url)
    if parsed.fragment:
        raise PermissionError('Fragments are not supported')
    # Select only a validated public address; no second DNS lookup in transport.
    ip = preflight['resolved_addresses'][0]
    if not ipaddress.ip_address(ip).is_global:
        raise PermissionError('Non-public destination')
    conn = connection_factory(preflight['hostname'], ip, timeout=min(5, remaining()))
    try:
        path = (parsed.path or '/') + (('?' + parsed.query) if parsed.query else '')
        conn.request('GET', path, headers={'Accept': 'application/json, text/plain', 'User-Agent': 'KalivNexus/0.10', 'Connection': 'close'})
        remaining()
        if getattr(conn, 'sock', None) is not None:
            conn.sock.settimeout(min(5, remaining()))
        response = conn.getresponse()
        if 300 <= response.status < 400:
            raise PermissionError('Redirects are blocked')
        content_length = response.getheader('Content-Length')
        if content_length and int(content_length) > MAX_BYTES:
            raise ValueError('Response exceeds size limit')
        remaining()
        if getattr(conn, 'sock', None) is not None:
            conn.sock.settimeout(min(5, remaining()))
        data = response.read(MAX_BYTES + 1)
        remaining()
        if len(data) > MAX_BYTES:
            raise ValueError('Response exceeds size limit')
        return {'status_code': response.status, 'body': data.decode('utf-8', errors='replace'), 'bytes': len(data)}
    finally:
        conn.close()
