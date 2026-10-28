"""Offline MCP Streamable HTTP framing checks (no outbound transport)."""
import json
from nexus.mcp_protocol import inspect_message, MAX_BYTES

ALLOWED_CONTENT_TYPES = frozenset({'application/json', 'text/event-stream'})


def inspect_http_response(content_type: str, body: bytes) -> dict:
    """Validate a bounded, single JSON-RPC response or SSE stream offline."""
    media_type = content_type.split(';', 1)[0].strip().lower()
    if media_type not in ALLOWED_CONTENT_TYPES:
        raise ValueError('Unsupported MCP response content type')
    if len(body) > MAX_BYTES:
        raise ValueError('MCP response exceeds size limit')
    try:
        data = body.decode('utf-8', errors='strict')
    except UnicodeDecodeError as exc:
        raise ValueError('MCP response is not UTF-8') from exc
    if media_type == 'application/json':
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError('Invalid JSON response') from exc
        info = inspect_message(payload)
        if info['kind'] != 'response':
            raise ValueError('Expected JSON-RPC response')
        return {'format': 'json', 'messages': 1, 'events': 0, 'connected': False}
    messages = 0
    events = 0
    for block in data.replace('\r\n', '\n').split('\n\n'):
        if not block.strip():
            continue
        fields = []
        for line in block.split('\n'):
            if line.startswith(':'):
                continue
            if line and not line.startswith(('data:', 'event:', 'id:', 'retry:')):
                raise ValueError('Invalid SSE field')
            fields.append(line)
        event = next((line[6:].strip() for line in fields if line.startswith('event:')), 'message')
        if event != 'message':
            raise ValueError('Unsupported SSE event type')
        payload_lines = [line[5:].lstrip(' ') for line in fields if line.startswith('data:')]
        if not payload_lines:
            continue
        try:
            payload = json.loads('\n'.join(payload_lines))
        except json.JSONDecodeError as exc:
            raise ValueError('Invalid SSE JSON') from exc
        inspect_message(payload)
        messages += 1
        events += 1
        if messages > 100:
            raise ValueError('Too many SSE messages')
    if not messages:
        raise ValueError('No MCP messages found')
    return {'format': 'sse', 'messages': messages, 'events': events, 'connected': False}
