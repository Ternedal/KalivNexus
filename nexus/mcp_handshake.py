"""Offline MCP initialize handshake validator. No outbound transport or execution."""
from nexus.mcp_protocol import inspect_message, PROTOCOL_VERSION


def validate_handshake(messages: list[dict]) -> dict:
    if not isinstance(messages, list) or len(messages) != 3:
        raise ValueError('Handshake requires exactly three messages')
    request, response, notification = messages
    for message in messages:
        inspect_message(message)
    if request.get('method') != 'initialize' or 'id' not in request:
        raise ValueError('First message must be an initialize request')
    params = request.get('params')
    if not isinstance(params, dict) or params.get('protocolVersion') != PROTOCOL_VERSION:
        raise ValueError('Unsupported client protocol version')
    if not isinstance(params.get('capabilities'), dict):
        raise ValueError('Missing client capabilities')
    client = params.get('clientInfo')
    if not isinstance(client, dict) or not all(isinstance(client.get(k), str) and client[k] for k in ('name', 'version')):
        raise ValueError('Missing client information')
    if response.get('id') != request['id'] or 'result' not in response:
        raise ValueError('Initialize response must match request id')
    result = response['result']
    if not isinstance(result, dict) or result.get('protocolVersion') != PROTOCOL_VERSION:
        raise ValueError('Unsupported server protocol version')
    if not isinstance(result.get('capabilities'), dict):
        raise ValueError('Missing server capabilities')
    server = result.get('serverInfo')
    if not isinstance(server, dict) or not all(isinstance(server.get(k), str) and server[k] for k in ('name', 'version')):
        raise ValueError('Missing server information')
    if notification.get('method') != 'notifications/initialized' or 'id' in notification:
        raise ValueError('Final message must be initialized notification')
    return {'valid': True, 'protocol_version': PROTOCOL_VERSION, 'server_name': server['name'], 'ready_for_transport': True, 'connected': False, 'executable': False}
