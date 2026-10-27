"""MCP initialize exchange over an injected, trusted transport.

No socket is opened here. A future network adapter must enforce egress policy,
DNS pinning, TLS hostname validation, response limits and network isolation.
"""
import json
from typing import Protocol
from nexus.mcp_handshake import validate_handshake
from nexus.mcp_protocol import PROTOCOL_VERSION

MAX_BODY = 1024 * 1024

class Transport(Protocol):
    def exchange(self, payload: bytes) -> tuple[int, str, bytes]: ...
    def notify(self, payload: bytes) -> None: ...


def initialize(transport: Transport) -> dict:
    request = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
        'protocolVersion': PROTOCOL_VERSION,
        'capabilities': {},
        'clientInfo': {'name': 'kaliv-nexus', 'version': '0.21.0'}}}
    status, content_type, body = transport.exchange(json.dumps(request).encode('utf-8'))
    if status != 200:
        raise ValueError('MCP initialize rejected')
    if content_type.split(';', 1)[0].strip().lower() != 'application/json':
        raise ValueError('Unsupported MCP initialize content type')
    if not isinstance(body, bytes) or len(body) > MAX_BODY:
        raise ValueError('Invalid MCP response size')
    try:
        response = json.loads(body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError('Invalid MCP response JSON') from exc
    notification = {'jsonrpc': '2.0', 'method': 'notifications/initialized'}
    result = validate_handshake([request, response, notification])
    transport.notify(json.dumps(notification).encode('utf-8'))
    return result | {'transport': 'injected', 'connected': False, 'executable': False}
