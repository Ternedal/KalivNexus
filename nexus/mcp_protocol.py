"""Offline MCP JSON-RPC envelope inspection. Never opens network connections."""
import json

MAX_BYTES = 1024 * 1024
PROTOCOL_VERSION = '2025-06-18'


def inspect_message(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError('JSON-RPC message must be an object')
    try:
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (TypeError, ValueError) as exc:
        raise ValueError('Message is not valid JSON') from exc
    if len(encoded) > MAX_BYTES:
        raise ValueError('Message exceeds size limit')
    if payload.get('jsonrpc') != '2.0':
        raise ValueError('Unsupported JSON-RPC version')
    has_method = 'method' in payload
    has_result = 'result' in payload
    has_error = 'error' in payload
    if has_method:
        if has_result or has_error:
            raise ValueError('Request cannot contain result or error')
        method = payload['method']
        if not isinstance(method, str) or not method or len(method) > 128:
            raise ValueError('Invalid method')
        if 'params' in payload and not isinstance(payload['params'], (dict, list)):
            raise ValueError('Invalid params')
        kind = 'request' if 'id' in payload else 'notification'
    else:
        if has_result == has_error or 'id' not in payload:
            raise ValueError('Response requires exactly one of result or error and an id')
        if has_error and (not isinstance(payload['error'], dict) or not isinstance(payload['error'].get('code'), int) or isinstance(payload['error'].get('code'), bool) or not isinstance(payload['error'].get('message'), str)):
            raise ValueError('Invalid error object')
        kind = 'response'
        method = None
    if 'id' in payload and (isinstance(payload['id'], bool) or not isinstance(payload['id'], (int, str)) or isinstance(payload['id'], str) and len(payload['id']) > 128):
        raise ValueError('Invalid request id')
    return {'kind': kind, 'method': method, 'protocol_version': PROTOCOL_VERSION, 'executable': False}


def session_transition(state: str, message: dict) -> str:
    """Pure state-machine check, not a live MCP session."""
    parsed = inspect_message(message)
    if state == 'new' and parsed['kind'] == 'request' and parsed['method'] == 'initialize':
        return 'initializing'
    if state == 'initializing' and parsed['kind'] == 'response' and 'result' in message and isinstance(message['result'], dict) and isinstance(message['result'].get('protocolVersion'), str):
        return 'initialized'
    if state == 'initialized' and parsed['kind'] == 'notification' and parsed['method'] == 'notifications/initialized':
        return 'ready'
    raise ValueError('Invalid session transition')
