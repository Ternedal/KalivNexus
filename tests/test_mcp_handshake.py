import copy
import pytest
from nexus.mcp_handshake import validate_handshake

@pytest.fixture
def transcript():
    return [
        {'jsonrpc':'2.0','id':7,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'Nexus','version':'0.20'}}},
        {'jsonrpc':'2.0','id':7,'result':{'protocolVersion':'2025-06-18','capabilities':{'tools':{}},'serverInfo':{'name':'demo','version':'1'}}},
        {'jsonrpc':'2.0','method':'notifications/initialized'},
    ]

def test_valid(transcript):
    result = validate_handshake(transcript)
    assert result['valid'] and not result['connected'] and not result['executable']

@pytest.mark.parametrize('mutate', [
    lambda t: t.pop(),
    lambda t: t[1].update(id=8),
    lambda t: t[0]['params'].update(protocolVersion='invalid'),
    lambda t: t[1]['result'].update(protocolVersion='invalid'),
    lambda t: t[2].update(id=1),
    lambda t: t[1]['result'].pop('serverInfo'),
    lambda t: t[0]['params'].pop('clientInfo'),
    lambda t: t[1].update(error={'code':-1,'message':'fail'}),
])
def test_reject(transcript, mutate):
    mutate(transcript)
    with pytest.raises(ValueError):
        validate_handshake(transcript)
