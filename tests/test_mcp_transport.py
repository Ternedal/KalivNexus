import json
import pytest
from nexus.mcp_transport import inspect_http_response

MSG = {'jsonrpc': '2.0', 'id': 1, 'result': {'protocolVersion': '2025-06-18'}}

def test_json_response():
    assert inspect_http_response('application/json; charset=utf-8', json.dumps(MSG).encode())['messages'] == 1

def test_sse_response():
    data = ('event: message\ndata: ' + json.dumps(MSG) + '\n\n').encode()
    assert inspect_http_response('text/event-stream', data)['messages'] == 1

def test_reject_request_as_response():
    with pytest.raises(ValueError):
        inspect_http_response('application/json', b'{"jsonrpc":"2.0","id":1,"method":"ping"}')

def test_reject_unsupported_type():
    with pytest.raises(ValueError):
        inspect_http_response('text/html', b'hello')

def test_reject_oversized():
    with pytest.raises(ValueError):
        inspect_http_response('application/json', b' ' * (1024 * 1024 + 1))

def test_reject_invalid_utf8():
    with pytest.raises(ValueError):
        inspect_http_response('application/json', b'\xff')

def test_reject_unknown_sse_event():
    with pytest.raises(ValueError):
        inspect_http_response('text/event-stream', b'event: endpoint\ndata: {}\n\n')
