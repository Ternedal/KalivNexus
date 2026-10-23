"""Validate approved HTTPS egress destinations; does not enforce network isolation."""
from dataclasses import dataclass
from urllib.parse import urlsplit
import ipaddress

class EgressDenied(PermissionError):
    pass

@dataclass(frozen=True)
class EgressGrant:
    origin: str
    methods: frozenset[str] = frozenset({'POST'})
    max_request_bytes: int = 1_048_576

def _origin(url: str) -> tuple[str, str, int]:
    try:
        u = urlsplit(url)
        if u.scheme != 'https' or not u.hostname or u.username or u.password or u.fragment:
            raise EgressDenied('Invalid HTTPS destination')
        if u.port not in (None, 443):
            raise EgressDenied('Only HTTPS port 443 allowed')
        host = u.hostname.lower().rstrip('.')
        if not host or host == 'localhost' or host.endswith(('.local', '.internal', '.localhost')):
            raise EgressDenied('Local destination denied')
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise EgressDenied('IP literals denied')
        if any(not label or len(label) > 63 for label in host.split('.')) or '.' not in host:
            raise EgressDenied('Invalid hostname')
        return ('https', host, 443)
    except (ValueError, TypeError, AttributeError) as exc:
        raise EgressDenied('Invalid destination') from exc

def authorize_egress(url: str, method: str, body: bytes, grant: EgressGrant) -> None:
    if not isinstance(grant, EgressGrant):
        raise EgressDenied('Explicit grant required')
    if _origin(url) != _origin(grant.origin):
        raise EgressDenied('Destination not in allowlist')
    if method not in grant.methods:
        raise EgressDenied('Method not allowed')
    if not isinstance(body, bytes) or len(body) > grant.max_request_bytes or grant.max_request_bytes < 0:
        raise EgressDenied('Request size exceeded')
