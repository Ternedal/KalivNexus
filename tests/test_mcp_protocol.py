import pytest
from nexus.mcp_protocol import inspect_message, session_transition


def test_initialize_sequence():
    req = {'jsonrpc':'2.0','id':1,'method':'initialize','params':{}}
    resp = {'jsonrpc':'2.0','id':1,'result':{'protocolVersion':'2025-06-18'}}
    note = {'jsonrpc':'2.0','method':'notifications/initialized'}
    assert session_transition('new',req) == 'initializing'
    assert session_transition('initializing',resp) == 'initialized'
    assert session_transition('initialized',note) == 'ready'

@pytest.mark.parametrize('payload', [
    {}, {'jsonrpc':'1.0','method':'initialize'},
    {'jsonrpc':'2.0','method':'tools/call','result':{}},
    {'jsonrpc':'2.0','id':True,'method':'initialize'},
    {'jsonrpc':'2.0','id':1,'error':{'code':True,'message':'bad'}},
    {'jsonrpc':'2.0','method':'x','params':'bad'},
    {'jsonrpc':'2.0','id':1,'result':{},'error':{'code':1,'message':'x'}},
])
def test_invalid_envelopes(payload):
    with pytest.raises(ValueError):
        inspect_message(payload)

def test_reject_out_of_order():
    with pytest.raises(ValueError):
        session_transition('new', {'jsonrpc':'2.0','method':'notifications/initialized'})

def test_size_limit():
    with pytest.raises(ValueError):
        inspect_message({'jsonrpc':'2.0','method':'x','params':{'data':'a'*1048576}})
