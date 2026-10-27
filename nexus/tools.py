"""Read-only unified tool discovery. MCP manifests are untrusted metadata, not executable tools."""
import json
import re

_NAME = re.compile(r'^[A-Za-z0-9_.-]{1,128}$')


def normalize_mcp_manifest(manifest: dict) -> list[dict]:
    if not isinstance(manifest, dict) or not isinstance(manifest.get('tools'), list):
        raise ValueError('Expected MCP tools/list-style manifest')
    if len(manifest['tools']) > 250 or len(json.dumps(manifest).encode()) > 1_000_000:
        raise ValueError('Manifest too large')
    result = []
    seen = set()
    for tool in manifest['tools']:
        if not isinstance(tool, dict) or not isinstance(tool.get('name'), str) or not _NAME.fullmatch(tool['name']):
            raise ValueError('Invalid tool name')
        if tool['name'] in seen:
            raise ValueError('Duplicate tool name')
        seen.add(tool['name'])
        schema = tool.get('inputSchema', {'type': 'object'})
        if not isinstance(schema, dict) or schema.get('type') != 'object':
            raise ValueError('Tool inputSchema must be an object schema')
        result.append({'id': 'mcp:' + tool['name'], 'provider': 'mcp', 'name': tool['name'],
                       'description': str(tool.get('description', ''))[:1000],
                       'input_schema': schema, 'status': 'discovered', 'executable': False})
    return result


def registered_openapi_tools(db, approved_only: bool = True) -> list[dict]:
    sql = '''SELECT spec_digest, operation_id, method, path, name, status, risk_level
             FROM api_operations'''
    if approved_only:
        sql += " WHERE status='approved'"
    sql += ' ORDER BY spec_digest, operation_id'
    return [{'id': 'openapi:' + r['spec_digest'] + ':' + r['operation_id'],
             'provider': 'openapi', 'name': r['name'], 'method': r['method'],
             'path': r['path'], 'status': r['status'], 'risk_level': r['risk_level'],
             'executable': False} for r in db.execute(sql)]
