"""Conservative OpenAPI 3 capability extraction (metadata only)."""
import hashlib
import json
from urllib.parse import urlparse

ALLOWED_METHODS = ('get', 'post', 'put', 'patch', 'delete')


def extract_operations(document: dict, *, max_operations: int = 250) -> list[dict]:
    if not isinstance(document, dict) or not str(document.get('openapi', '')).startswith('3.'):
        raise ValueError('OpenAPI 3 document required')
    paths = document.get('paths')
    if not isinstance(paths, dict):
        raise ValueError('paths must be an object')
    servers = document.get('servers', [])
    if not isinstance(servers, list) or not servers or not isinstance(servers[0], dict):
        raise ValueError('Absolute HTTPS server URL required')
    base = servers[0].get('url', '')
    parsed = urlparse(base)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Absolute HTTPS server URL required')
    result = []
    for path, path_item in paths.items():
        if not isinstance(path, str) or not path.startswith('/') or not isinstance(path_item, dict):
            raise ValueError('Invalid path item')
        for method in ALLOWED_METHODS:
            operation = path_item.get(method)
            if operation is None:
                continue
            if not isinstance(operation, dict):
                raise ValueError('Invalid operation')
            key = f'{method.upper()} {path}'
            result.append({
                'id': hashlib.sha256((base + '|' + key).encode()).hexdigest()[:24],
                'method': method.upper(), 'path': path,
                'name': str(operation.get('summary') or operation.get('operationId') or key)[:200],
                'description': str(operation.get('description') or '')[:2000],
                'server_url': base,
                'requires_review': True,
                'executable': False,
            })
            if len(result) > max_operations:
                raise ValueError('Too many operations')
    return result
