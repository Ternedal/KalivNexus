import json
import pytest
from nexus.mcp_pipeline import inspect_session_tools
from test_mcp_reconcile import setup
from nexus.mcp_sessions import transition_session
from nexus.mcp_protocol import PROTOCOL_VERSION


class FakeTransport:
    def __init__(self, tools):
        self.tools = tools
        self.calls = []
        self.notifications = []

    def exchange(self, payload):
        req = json.loads(payload)
        self.calls.append(req['method'])
        if req['method'] == 'initialize':
            result = {'protocolVersion': PROTOCOL_VERSION,
                      'capabilities': {'tools': {}},
                      'serverInfo': {'name': 'fake', 'version': '1.0'}}
        elif req['method'] == 'tools/list':
            result = {'tools': self.tools}
        else:
            raise AssertionError('Unexpected request')
        return 200, 'application/json', json.dumps({'jsonrpc':'2.0','id':req['id'],'result':result}).encode()

    def notify(self, payload):
        self.notifications.append(json.loads(payload))


def test_pipeline_matches_without_execution():
    db, sid, tool, _ = setup()
    transport = FakeTransport([tool])
    result = inspect_session_tools(db, sid, transport)
    assert result['reconciliation']['manifest_matches']
    assert result['execution_allowed'] is False
    assert transport.calls == ['initialize', 'tools/list']
    assert transport.notifications[0]['method'] == 'notifications/initialized'


def test_pipeline_detects_drift():
    db, sid, tool, _ = setup()
    changed = dict(tool, description='Unexpected change')
    result = inspect_session_tools(db, sid, FakeTransport([changed]))
    assert result['reconciliation']['changed'] == ['weather']
    assert not result['reconciliation']['manifest_matches']


def test_pipeline_denies_closed_session_before_transport():
    db, sid, tool, _ = setup()
    transition_session(db, sid, 'closed')
    transport = FakeTransport([tool])
    with pytest.raises(ValueError, match='ready'):
        inspect_session_tools(db, sid, transport)
    assert transport.calls == []


def test_pipeline_fails_closed_on_transport_error():
    db, sid, tool, _ = setup()
    class Broken(FakeTransport):
        def exchange(self, payload):
            raise ConnectionError('simulated failure')
    with pytest.raises(ConnectionError):
        inspect_session_tools(db, sid, Broken([tool]))
