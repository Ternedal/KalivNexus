from fastapi.testclient import TestClient
from nexus.main import app
from nexus.openapi import extract_operations
import pytest

DOC = {'openapi': '3.0.3', 'servers': [{'url': 'https://example.org/api'}], 'paths': {'/items': {'get': {'summary': 'List items'}, 'post': {'summary': 'Create item'}}}}

def test_extract():
    ops = extract_operations(DOC)
    assert len(ops) == 2
    assert all(not o['executable'] and o['requires_review'] for o in ops)

def test_reject_insecure_server():
    with pytest.raises(ValueError):
        extract_operations({**DOC, 'servers': [{'url': 'http://localhost:8000'}]})

def test_endpoint_auth_and_inspect():
    with TestClient(app) as client:
        assert client.post('/v1/openapi/inspect', json={'document': DOC}).status_code == 401
        r = client.post('/v1/openapi/inspect', json={'document': DOC}, headers={'Authorization': 'Bearer test-secret'})
        assert r.status_code == 200
        assert r.json()['count'] == 2

