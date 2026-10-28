"""Static risk assessment for untrusted OpenAPI operations; never performs I/O."""
from urllib.parse import urlsplit
import ipaddress

WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
SENSITIVE_TERMS = ('payment', 'billing', 'transfer', 'delete', 'admin', 'token', 'secret', 'password')


def assess_operation(operation: dict, document: dict) -> dict:
    method = operation['method']
    path = operation['path'].lower()
    url = urlsplit(operation['server_url'])
    hostname = (url.hostname or '').lower().rstrip('.')
    flags = []
    if method in WRITE_METHODS:
        flags.append('state_changing_method')
    if any(term in path for term in SENSITIVE_TERMS):
        flags.append('sensitive_path')
    if hostname == 'localhost' or hostname.endswith(('.local', '.internal', '.localhost')):
        flags.append('private_hostname')
    try:
        if not ipaddress.ip_address(hostname).is_global:
            flags.append('non_public_ip')
    except ValueError:
        pass
    if url.port not in (None, 443):
        flags.append('non_standard_port')
    # Document-level security is not proof of operation-level protection.
    paths = document.get('paths', {})
    op = paths.get(operation['path'], {}).get(method.lower(), {})
    security = op.get('security', document.get('security', None))
    if security is None or security == []:
        flags.append('no_declared_auth')
    level = 'high' if any(x in flags for x in ('sensitive_path', 'private_hostname', 'non_public_ip')) else ('medium' if flags else 'low')
    return {'risk_level': level, 'risk_flags': flags, 'requires_explicit_approval': True, 'executable': False}
