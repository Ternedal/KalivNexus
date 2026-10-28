import pytest
from nexus.egress_proxy_policy import EgressGrant, EgressDenied, authorize_egress

def test_approved_https_origin():
    authorize_egress('https://api.example.com/mcp', 'POST', b'{}', EgressGrant('https://api.example.com/mcp'))

@pytest.mark.parametrize('url', [
    'http://api.example.com/mcp',
    'https://127.0.0.1/mcp',
    'https://localhost/mcp',
    'https://api.example.com:8443/mcp',
    'https://other.example.com/mcp',
    'https://user:pass@api.example.com/mcp',
])
def test_reject_unapproved_destination(url):
    with pytest.raises(EgressDenied):
        authorize_egress(url, 'POST', b'{}', EgressGrant('https://api.example.com/mcp'))

def test_reject_method_and_oversized_body():
    grant = EgressGrant('https://api.example.com/mcp', max_request_bytes=2)
    with pytest.raises(EgressDenied):
        authorize_egress(grant.origin, 'GET', b'', grant)
    with pytest.raises(EgressDenied):
        authorize_egress(grant.origin, 'POST', b'123', grant)
