import json
import pytest
from nexus.mcp_client import initialize

class FakeTransport:
    def __init__(self, status=200, content_type='application/json', response=None):
        self.status, self.content_type = status, content_type
        self.response = response
        self.notifications = []
        self.requests = []

    def exchange(self, payload):
        self.requests.append(json.loads(payload))
        response = self.response if self.response is not None else {
            'jsonrpc': '2.0', 'id': 1, 'result': {
                'protocolVersion': '2025-06-18', 'capabilities': {},
                'serverInfo': {'name': 'fake', 'version': '1'}}}
        return self.status, self.content_type, json.dumps(response).encode()

    def notify(self, payload):
        self.notifications.append(json.loads(payload))

def test_initialize_exchange():
    t = FakeTransport()
    result = initialize(t)
    assert result['valid'] and not result['connected'] and not result['executable']
    assert t.requests[0]['method'] == 'initialize'
    assert t.notifications[0]['method'] == 'notifications/initialized'

@pytest.mark.parametrize('kwargs', [
    {'status': 401}, {'content_type': 'text/html'},
    {'response': {'jsonrpc': '2.0', 'id': 99, 'result': {}}},
    {'response': {'jsonrpc': '2.0', 'id': 1, 'error': {'code': -1, 'message': 'fail'}}},
])
def test_fail_closed(kwargs):
    t = FakeTransport(**kwargs)
    with pytest.raises(ValueError):
        initialize(t)
    assert not t.notifications
