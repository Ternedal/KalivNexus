import pytest
from nexus.mcp_relay_client import AttestedMCPRelayTransport

class NoNetwork:
    def __init__(self): self.calls = 0
    def __call__(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError('Network must not be contacted')

@pytest.mark.parametrize('payload', [
    b'{"jsonrpc":"2.0","id":1,"method":"tools/list","method":"tools/call"}',
    b'{"jsonrpc":"2.0","id":1,"method":"tools/call","method":"tools/list"}',
    b'{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{"a":1,"a":2}}',
    b'[{"jsonrpc":"2.0","id":1,"method":"tools/list"}]',
    b'{"jsonrpc":"2.0","id":true,"method":"tools/list"}',
    b'{"jsonrpc":"2.0","method":"tools/list"}',
    b'{"jsonrpc":"2.0","id":1,"method":"notifications/initialized"}',
    b'{"jsonrpc":"2.0","id":1,"method":"tools/list","params":null}',
    b'{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{"x":NaN}}',
])
def test_invalid_requests_do_not_contact_relay(payload):
        network = NoNetwork()
        transport = AttestedMCPRelayTransport(expected_upstream='https://mcp.example.org/mcp',
                        host='relay', secret='x'*40, enabled=True, connection_factory=network)
        with pytest.raises((ValueError, PermissionError)):
            transport.exchange(payload)
        assert network.calls == 0
