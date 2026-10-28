import pytest
from nexus.mcp_client import initialize
from nexus.mcp_discovery import discover_tools
from nexus.mcp_test_harness import local_mcp_server, LoopbackFixtureTransport

def test_live_loopback_handshake_and_discovery():
    with local_mcp_server() as url:
        transport = LoopbackFixtureTransport(url)
        assert initialize(transport)['valid'] is True
        result = discover_tools(transport)
        assert result['count'] == 1
        assert result['tools'][0]['name'] == 'echo'
        assert result['executable'] is False

def test_unknown_tool_call_is_rejected():
    import json
    with local_mcp_server() as url:
        status, _, body = LoopbackFixtureTransport(url).exchange(json.dumps({'jsonrpc':'2.0','id':42,'method':'tools/call'}).encode())
        assert status == 200
        assert json.loads(body)['error']['code'] == -32601

def test_non_loopback_address_rejected():
    with pytest.raises(ValueError):
        LoopbackFixtureTransport('https://example.com/mcp')

def test_non_fixture_path_rejected():
    with pytest.raises(ValueError):
        LoopbackFixtureTransport('http://127.0.0.1:1234/admin')
