import pytest
from nexus.mcp_relay_client import MCPRelayTransport

SECRET = "s" * 40

@pytest.mark.parametrize("host", ["relay-1", "relay.internal", "a" * 63 + ".internal"])
def test_valid_relay_dns_names(host):
    assert MCPRelayTransport(host=host, secret=SECRET, enabled=True).host == host

@pytest.mark.parametrize("host", ["-relay", "relay-", "relay..internal", "relay.", ".relay", "relay_.internal", "127.0.0.1", "a" * 64 + ".internal", "a" * 254, "", "relay/internal"])
def test_invalid_relay_dns_names_rejected(host):
    with pytest.raises(ValueError, match="Invalid relay hostname"):
        MCPRelayTransport(host=host, secret=SECRET, enabled=True)

