"""Opt-in pinned HTTPS MCP Streamable HTTP transport (JSON response subset).

This transport is NOT a network sandbox. Deploy only behind enforced egress rules.
"""
import json
import re
from urllib.parse import urlsplit

from nexus.egress import inspect_target
from nexus.executor import PinnedHTTPSConnection

MAX_BODY = 1024 * 1024
SESSION_RE = re.compile(r'^[\x21-\x7e]{1,256}$')


class MCPNetworkTransport:
    def __init__(self, url, *, enabled=False, resolver=None, connection_factory=PinnedHTTPSConnection):
        if not enabled:
            raise PermissionError('MCP network transport is disabled by default')
        self.url = url
        self.resolver = resolver
        self.connection_factory = connection_factory
        self.session_id = None

    def _auth_headers(self):
        return {}

    def _post(self, payload):
        if not isinstance(payload, bytes) or len(payload) > MAX_BODY:
            raise ValueError('Invalid MCP request size')
        try:
            message = json.loads(payload)
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError('Invalid JSON-RPC request') from exc
        if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
            raise ValueError('Invalid JSON-RPC envelope')
        parsed = urlsplit(self.url)
        if parsed.fragment or parsed.username or parsed.password:
            raise PermissionError('Unsupported MCP URL')
        preflight = inspect_target(self.url, resolver=self.resolver)
        conn = self.connection_factory(preflight['hostname'], preflight['resolved_addresses'][0], timeout=5)
        try:
            headers = {'Content-Type': 'application/json', 'Accept': 'application/json',
                       'Connection': 'close', 'User-Agent': 'KalivNexus/0.22'}
            headers.update(self._auth_headers())
            if self.session_id:
                headers['Mcp-Session-Id'] = self.session_id
            path = (parsed.path or '/') + ('?' + parsed.query if parsed.query else '')
            conn.request('POST', path, body=payload, headers=headers)
            response = conn.getresponse()
            if 300 <= response.status < 400:
                raise PermissionError('Redirects are blocked')
            length = response.getheader('Content-Length')
            if length is not None and int(length) > MAX_BODY:
                raise ValueError('MCP response too large')
            body = response.read(MAX_BODY + 1)
            if len(body) > MAX_BODY:
                raise ValueError('MCP response too large')
            session = response.getheader('Mcp-Session-Id')
            if session is not None:
                if not SESSION_RE.fullmatch(session):
                    raise ValueError('Invalid MCP session ID')
                if self.session_id is not None and session != self.session_id:
                    raise ValueError('Unexpected MCP session change')
                self.session_id = session
            content_type = response.getheader('Content-Type') or ''
            return response.status, content_type, body
        finally:
            conn.close()

    def exchange(self, payload):
        status, content_type, body = self._post(payload)
        if content_type.split(';', 1)[0].strip().lower() != 'application/json':
            raise ValueError('Only JSON MCP responses are supported')
        return status, content_type, body

    def notify(self, payload):
        status, _, body = self._post(payload)
        if status != 202 or body:
            raise ValueError('Unexpected MCP notification acknowledgement')
