import pytest
from nexus.tools import normalize_mcp_manifest


def test_mcp_manifest_normalization():
    tools = normalize_mcp_manifest({'tools': [{'name': 'weather.lookup', 'description': 'Forecast', 'inputSchema': {'type': 'object'}}]})
    assert tools[0]['id'] == 'mcp:weather.lookup'
    assert tools[0]['executable'] is False

@pytest.mark.parametrize('manifest', [
    {'tools': [{'name': '../bad'}]},
    {'tools': [{'name': 'a'}, {'name': 'a'}]},
    {'tools': [{'name': 'a', 'inputSchema': {'type': 'string'}}]},
    {'tools': 'invalid'},
])
def test_reject_invalid_manifest(manifest):
    with pytest.raises(ValueError):
        normalize_mcp_manifest(manifest)
