"""Fail-closed execution planning. This module NEVER makes outbound requests."""
import ipaddress
import json
import re
from urllib.parse import urlsplit, urlunsplit, quote

PLACEHOLDER = re.compile(r'\{([A-Za-z_][A-Za-z0-9_]*)\}')


def plan(db, digest: str, operation_id: str, parameters: dict) -> dict:
    row = db.execute('''SELECT s.document, o.status, o.method, o.path, o.risk_level
                        FROM api_operations o JOIN api_specs s ON s.digest=o.spec_digest
                        WHERE o.spec_digest=? AND o.operation_id=?''', (digest, operation_id)).fetchone()
    if row is None:
        raise LookupError('Operation not found')
    if row['status'] != 'approved':
        raise PermissionError('Operation must be approved before planning')
    if row['method'] != 'GET':
        raise PermissionError('Only read-only GET operations can be planned')
    if row['risk_level'] == 'high':
        raise PermissionError('High-risk operations cannot be planned')
    document = json.loads(row['document'])
    base = document['servers'][0]['url']
    url = urlsplit(base)
    host = (url.hostname or '').lower().rstrip('.')
    if url.scheme != 'https' or url.username or url.password or url.fragment or url.port not in (None, 443):
        raise PermissionError('Unsafe server URL')
    if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')) or not host or '.' not in host:
        raise PermissionError('Non-public hostname')
    try:
        if not ipaddress.ip_address(host).is_global:
            raise PermissionError('Non-public IP')
    except ValueError:
        pass
    if not isinstance(parameters, dict) or len(parameters) > 20:
        raise ValueError('Invalid parameters')
    keys = set(PLACEHOLDER.findall(row['path']))
    if set(parameters) != keys:
        raise ValueError('Path parameters must match placeholders exactly')
    path = row['path']
    for key in keys:
        value = parameters[key]
        if not isinstance(value, str) or not value or len(value) > 128 or any(ord(c) < 32 for c in value):
            raise ValueError('Invalid path parameter')
        path = path.replace('{' + key + '}', quote(value, safe=''))
    # The path is displayed only, never dereferenced. DNS and network-layer policy
    # must be added before implementing actual execution.
    target = urlunsplit(('https', url.netloc, url.path.rstrip('/') + path, '', ''))
    return {'spec_digest': digest, 'operation_id': operation_id, 'method': 'GET',
            'target_url': target, 'risk_level': row['risk_level'],
            'execution_enabled': False, 'requires_runtime_egress_policy': True}
