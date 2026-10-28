"""Bounded, read-only MCP tools/list discovery over an injected transport.

Discovery never approves, registers, or executes tools. The caller is responsible
for establishing an authorized, initialized session and securing its transport.
"""
import json
from nexus.tools import normalize_mcp_manifest

MAX_RESPONSE_BYTES = 1024 * 1024
MAX_PAGES = 10
MAX_TOOLS = 250


def discover_tools(transport, *, max_pages=MAX_PAGES):
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or not 1 <= max_pages <= MAX_PAGES:
        raise ValueError('Invalid MCP page limit')
    cursor = None
    seen_cursors = set()
    collected = []
    names = set()
    for page in range(max_pages):
        request = {'jsonrpc': '2.0', 'id': page + 2, 'method': 'tools/list'}
        if cursor is not None:
            request['params'] = {'cursor': cursor}
        status, content_type, body = transport.exchange(json.dumps(request).encode('utf-8'))
        if status != 200 or content_type.split(';', 1)[0].strip().lower() != 'application/json':
            raise ValueError('Invalid MCP tools/list HTTP response')
        if not isinstance(body, bytes) or len(body) > MAX_RESPONSE_BYTES:
            raise ValueError('MCP tools/list response exceeds limit')
        try:
            response = json.loads(body.decode('utf-8'))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError('Invalid MCP tools/list JSON') from exc
        if not isinstance(response, dict) or response.get('jsonrpc') != '2.0' or type(response.get('id')) is not int or response['id'] != page + 2 or 'error' in response:
            raise ValueError('Invalid MCP tools/list RPC response')
        result = response.get('result')
        if not isinstance(result, dict):
            raise ValueError('Invalid MCP tools/list result')
        tools = result.get('tools')
        if not isinstance(tools, list) or len(tools) + len(collected) > MAX_TOOLS:
            raise ValueError('Invalid MCP tools/list size')
        normalized = normalize_mcp_manifest({'tools': tools})
        for item in normalized:
            if item['name'] in names:
                raise ValueError('Duplicate MCP tool across pages')
            names.add(item['name'])
        collected.extend(tools)
        next_cursor = result.get('nextCursor')
        if next_cursor is None:
            return {'tools': normalize_mcp_manifest({'tools': collected}), 'pages': page + 1,
                    'count': len(collected), 'executable': False, 'approved': False}
        if not isinstance(next_cursor, str) or not next_cursor or len(next_cursor) > 2048 or next_cursor in seen_cursors:
            raise ValueError('Invalid or repeated MCP cursor')
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    raise ValueError('MCP tools/list page limit exceeded')
