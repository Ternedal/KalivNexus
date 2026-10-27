"""Opt-in MCP JSON transport through the isolated relay; never contacts upstream directly.

The network boundary is provided by deployment, NOT this Python module.
"""
import hmac
import http.client
import json
import re
from nexus.relay_attestation import new_challenge, verify

MAX_BODY = 1024 * 1024
READ_ONLY_METHODS = frozenset(('initialize', 'notifications/initialized', 'tools/list'))
_HOST_LABEL = re.compile(r'^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$')
# Same rule as nexus.mcp_network.SESSION_RE; kept local so the relay client does not
# import the direct-network transport.
SESSION_RE = re.compile(r'^[\x21-\x7e]{1,256}$')


def _valid_relay_host(host: str) -> bool:
    # Reject malformed DNS labels, trailing dots and ambiguous numeric hosts.
    if not isinstance(host, str) or len(host) > 253 or not host or host.endswith('.'):
        return False
    labels = host.split('.')
    return all(_HOST_LABEL.fullmatch(label) for label in labels) and not all(label.isdigit() for label in labels)



def _reject_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError('Duplicate JSON key')
        obj[key] = value
    return obj


def _read_only_request(payload: bytes) -> dict:
    if not isinstance(payload, bytes) or len(payload) > MAX_BODY:
        raise ValueError('Invalid MCP request size')
    try:
        message = json.loads(payload, object_pairs_hook=_reject_duplicate_keys,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid JSON constant')))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError('Invalid JSON-RPC payload') from exc
    if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
        raise ValueError('Invalid JSON-RPC request')
    method = message.get('method')
    if not isinstance(method, str) or method not in READ_ONLY_METHODS:
        raise PermissionError('Relay method not approved for read-only inspection')
    if 'id' in message and (isinstance(message['id'], bool) or not isinstance(message['id'], (str, int))):
        raise ValueError('Invalid JSON-RPC request ID')
    if method == 'notifications/initialized':
        if 'id' in message:
            raise ValueError('Notification must not have ID')
    elif 'id' not in message:
        raise ValueError('Request ID required')
    if 'params' in message and not isinstance(message['params'], (dict, list)):
        raise ValueError('Invalid JSON-RPC params')
    return message


class MCPRelayTransport:
    def __init__(self, *, host: str, secret: str, port: int = 8787,
                 enabled: bool = False, connection_factory=http.client.HTTPConnection):
        if not enabled:
            raise PermissionError('MCP relay transport disabled by default')
        if not _valid_relay_host(host):
            raise ValueError('Invalid relay hostname')
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise ValueError('Invalid relay port')
        if not isinstance(secret, str) or len(secret) < 32 or any(ord(c) < 33 or ord(c) > 126 for c in secret):
            raise ValueError('Strong relay secret required')
        self.host, self.port, self._secret = host, port, secret
        self._connection_factory = connection_factory
        # The upstream MCP session, carried by this client across relay requests
        # because the relay itself is stateless (Codex P2 on #39).
        self.session_id = None

    def attest(self, expected_upstream: str) -> None:
        """Verify the relay reports the expected configured target, not OS isolation."""
        challenge = new_challenge()
        conn = self._connection_factory(self.host, self.port, timeout=5)
        try:
            conn.request('GET', '/attest', headers={
                'Authorization': 'Bearer ' + self._secret,
                'X-Nexus-Challenge': challenge,
                'Connection': 'close',
            })
            response = conn.getresponse()
            if response.status != 200:
                raise PermissionError('Relay attestation rejected')
            content_type = (response.getheader('Content-Type') or '').split(';', 1)[0].strip().lower()
            if content_type != 'application/json':
                raise PermissionError('Relay attestation rejected')
            length = response.getheader('Content-Length')
            if length is not None and (not length.isdecimal() or int(length) > 4096):
                raise PermissionError('Relay attestation rejected')
            verify(self._secret, challenge, expected_upstream, response.read(4097))
        finally:
            conn.close()

    def _post(self, payload: bytes):
        _read_only_request(payload)
        conn = self._connection_factory(self.host, self.port, timeout=5)
        try:
            headers = {
                'Authorization': 'Bearer ' + self._secret,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Connection': 'close',
            }
            if self.session_id:
                headers['Mcp-Session-Id'] = self.session_id
            conn.request('POST', '/mcp', body=payload, headers=headers)
            response = conn.getresponse()
            length = response.getheader('Content-Length')
            if length is not None and (not length.isdecimal() or int(length) > MAX_BODY):
                raise ValueError('Relay response too large')
            body = response.read(MAX_BODY + 1)
            if len(body) > MAX_BODY:
                raise ValueError('Relay response too large')
            if response.status != 200 and response.status != 202:
                raise PermissionError('Relay rejected request')
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

    def exchange(self, payload: bytes):
        status, content_type, body = self._post(payload)
        if status != 200 or content_type.split(';', 1)[0].strip().lower() != 'application/json':
            raise ValueError('Unexpected MCP relay response')
        return status, content_type, body

    def notify(self, payload: bytes):
        status, _, body = self._post(payload)
        if status != 202 or body:
            raise ValueError('Unexpected MCP relay notification acknowledgement')


class AttestedMCPRelayTransport(MCPRelayTransport):
    """Read-only relay transport that challenges upstream configuration before each request.

    This is a configuration check, not a proof of network isolation or a guarantee
    against a compromised relay changing its configuration after attestation.
    """

    def __init__(self, *, expected_upstream: str, **kwargs):
        from nexus.relay_attestation import fingerprint
        fingerprint(expected_upstream)  # reject malformed upstream before any I/O
        super().__init__(**kwargs)
        self.expected_upstream = expected_upstream

    def _post(self, payload: bytes):
        # Reject malformed or ambiguous requests before contacting the relay.
        _read_only_request(payload)
        self.attest(self.expected_upstream)
        return super()._post(payload)
