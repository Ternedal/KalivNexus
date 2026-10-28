"""End-to-end initialize -> notify -> list -> reconcile over a fake HTTP relay."""
import json
import pytest
from nexus.mcp_pipeline import inspect_via_relay
from nexus.mcp_protocol import PROTOCOL_VERSION
from nexus.mcp_sessions import transition_session
from test_mcp_reconcile import setup
from nexus.mcp_relay_client import MCPRelayTransport

SECRET = 'r' * 48
UPSTREAM = 'https://api.example.com/mcp'


class Response:
    status = 200
    def __init__(self, request, tools):
        self.request = request
        self.tools = tools
        if request['method'] == 'notifications/initialized':
            self.status = 202
            self.body = b''
        else:
            result = ({'protocolVersion': PROTOCOL_VERSION, 'capabilities': {'tools': {}},
                       'serverInfo': {'name': 'relay-test', 'version': '1'}}
                      if request['method'] == 'initialize' else {'tools': tools})
            self.body = json.dumps({'jsonrpc': '2.0', 'id': request['id'], 'result': result}).encode()

    def getheader(self, key):
        return {'Content-Type': 'application/json', 'Content-Length': str(len(self.body))}.get(key)

    def read(self, n):
        return self.body[:n]


class Connection:
    def __init__(self, host, port, timeout, *, calls, tools):
        assert (host, port, timeout) == ('relay', 8787, 5)
        self.calls, self.tools = calls, tools

    def request(self, method, path, body, headers):
        assert (method, path) == ('POST', '/mcp')
        assert headers['Authorization'] == 'Bearer ' + SECRET
        self.req = json.loads(body)
        self.calls.append(self.req['method'])

    def getresponse(self):
        return Response(self.req, self.tools)

    def close(self):
        pass


def factory(calls, tools):
    return lambda host, port, timeout: Connection(host, port, timeout, calls=calls, tools=tools)


def test_relay_end_to_end_read_only():
    db, sid, tool, _ = setup()
    calls = []
    result = inspect_via_relay(db, sid, relay_host='relay', relay_secret=SECRET,
                               enabled=True, upstream_url=UPSTREAM, connection_factory=factory(calls, [tool]))
    assert calls == ['initialize', 'notifications/initialized', 'tools/list']
    assert result['reconciliation']['manifest_matches']
    assert result['execution_allowed'] is False
    assert result['isolation_verified'] is False
    assert result['transport'] == 'relay'


def test_relay_disabled_without_any_calls():
    db, sid, tool, _ = setup()
    calls = []
    with pytest.raises(PermissionError, match='disabled'):
        inspect_via_relay(db, sid, relay_host='relay', relay_secret=SECRET,
                          connection_factory=factory(calls, [tool]))
    assert not calls


def test_relay_closed_session_without_any_calls():
    db, sid, tool, _ = setup()
    transition_session(db, sid, 'closed')
    calls = []
    with pytest.raises(ValueError, match='ready'):
        inspect_via_relay(db, sid, relay_host='relay', relay_secret=SECRET,
                          enabled=True, upstream_url=UPSTREAM, connection_factory=factory(calls, [tool]))
    assert not calls


def test_relay_detects_manifest_drift_without_approval():
    db, sid, tool, _ = setup()
    result = inspect_via_relay(db, sid, relay_host='relay', relay_secret=SECRET,
                               enabled=True, upstream_url=UPSTREAM, connection_factory=factory([], [dict(tool, description='drift')]))
    assert not result['reconciliation']['manifest_matches']
    assert not result['execution_allowed']


def test_relay_requires_upstream_binding_before_network():
    db, sid, tool, _ = setup()
    calls = []
    with pytest.raises(PermissionError, match='binding required'):
        inspect_via_relay(db, sid, relay_host='relay', relay_secret=SECRET,
                          enabled=True, connection_factory=factory(calls, [tool]))
    assert calls == []


def test_relay_rejects_upstream_mismatch_before_network():
    db, sid, tool, _ = setup()
    calls = []
    with pytest.raises(PermissionError, match='binding mismatch'):
        inspect_via_relay(db, sid, relay_host='relay', relay_secret=SECRET,
                          upstream_url='https://evil.example/mcp', enabled=True,
                          connection_factory=factory(calls, [tool]))
    assert calls == []


@pytest.mark.parametrize('method', ['tools/call', 'resources/read', 'ping'])
def test_relay_rejects_non_discovery_methods_before_network(method):
    calls = []
    transport = MCPRelayTransport(host='relay', secret=SECRET, enabled=True,
                                  connection_factory=factory(calls, []))
    with pytest.raises(PermissionError, match='read-only'):
        transport.exchange(json.dumps({'jsonrpc':'2.0', 'id':1, 'method':method}).encode())
    assert calls == []
