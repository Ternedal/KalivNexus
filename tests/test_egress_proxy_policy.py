import pytest
from nexus.egress_proxy_policy import EgressGrant, EgressDenied, authorize_egress

GRANT = EgressGrant('https://mcp.example.com')

def test_matching_origin():
    authorize_egress('https://mcp.example.com/mcp', 'POST', b'{}', GRANT)

@pytest.mark.parametrize('url', [
    'http://mcp.example.com', 'https://localhost/mcp',
    'https://127.0.0.1/mcp', 'https://10.0.0.1/mcp',
    'https://mcp.example.com.evil.test/mcp', 'https://mcp.example.com:8443/mcp',
    'https://user:pass@mcp.example.com/mcp', 'https://mcp.example.com/mcp#frag',
])
def test_deny_unsafe_destinations(url):
    with pytest.raises(EgressDenied):
        authorize_egress(url, 'POST', b'{}', GRANT)

def test_deny_unapproved_method():
    with pytest.raises(EgressDenied):
        authorize_egress('https://mcp.example.com/mcp', 'DELETE', b'', GRANT)

def test_deny_oversize():
    with pytest.raises(EgressDenied):
        authorize_egress('https://mcp.example.com/mcp', 'POST', b'x'*1_048_577, GRANT)

def test_deny_missing_grant():
    with pytest.raises(EgressDenied):
        authorize_egress('https://mcp.example.com/mcp', 'POST', b'', None)
