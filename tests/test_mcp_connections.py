import pytest
from fastapi.testclient import TestClient
from nexus.mcp_connections import validate_profile
from nexus.main import app
import nexus.main as main
import nexus.db as dbmodule

@pytest.mark.parametrize('url', ['http://example.com/mcp', 'https://localhost/mcp', 'https://127.0.0.1/mcp', 'https://user:pass@example.com/mcp', 'https://example.com:8443/mcp', 'https://example.com/#fragment', 'https://example.local/mcp'])
def test_reject_unsafe_profiles(url):
    with pytest.raises(ValueError):
        validate_profile('demo', url)

def test_accept_public_hostname_without_connecting():
    assert validate_profile('demo', 'https://mcp.example.com/mcp')[0] == 'demo'

def test_api_connection_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmodule, 'DB_PATH', tmp_path / 'nexus.db')
    monkeypatch.setattr(main, 'TOKEN', 'test-token')
    client = TestClient(app)
    headers = {'Authorization': 'Bearer test-token'}
    manifest = client.post('/v1/mcp/manifests', headers=headers, json={'tools':[{'name':'lookup'}]})
    assert manifest.status_code == 200
    digest = manifest.json()['digest']
    response = client.post('/v1/mcp/connections', headers=headers, json={'name':'demo','url':'https://mcp.example.com/mcp','manifest_digest':digest})
    assert response.status_code == 201, response.text
    assert response.json()['connected'] is False
    assert response.json()['enabled'] is False
    assert client.get('/v1/mcp/connections').status_code in (401,503)
    data = client.get('/v1/mcp/connections',headers=headers).json()
    assert len(data['connections']) == 1
    assert data['execution_enabled'] is False
    assert client.post('/v1/mcp/connections',headers=headers,json={'name':'demo','url':'https://mcp.example.com/mcp','manifest_digest':digest}).status_code == 422
