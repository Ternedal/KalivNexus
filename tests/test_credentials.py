import pytest
from nexus.credentials import CredentialBinding, bearer_headers, redact_headers, validate_secret_ref


def test_reference_validation():
    assert validate_secret_ref('NEXUS_MCP_TOKEN') == 'NEXUS_MCP_TOKEN'
    for bad in ('a', '../SECRET', 'token name', '', 'a'*200):
        with pytest.raises(ValueError):
            validate_secret_ref(bad)


def test_binding_validation():
    with pytest.raises(ValueError):
        CredentialBinding('../unsafe', 'VALID_TOKEN')


def test_resolve_at_call_time():
    binding = CredentialBinding('my-server', 'NEXUS_MCP_TOKEN')
    assert bearer_headers(binding, lambda ref: 'abc123') == {'Authorization': 'Bearer abc123'}


def test_unavailable_secret_fails_closed():
    binding = CredentialBinding('my-server', 'NEXUS_MCP_TOKEN')
    with pytest.raises(PermissionError, match='Credential unavailable') as exc:
        bearer_headers(binding, lambda ref: (_ for _ in ()).throw(RuntimeError('private secret')))
    assert 'private secret' not in str(exc.value)


def test_header_redaction():
    assert redact_headers({'Authorization':'Bearer abc', 'X-Api-Key':'abc', 'Accept':'application/json'}) == {
        'Authorization':'[REDACTED]', 'X-Api-Key':'[REDACTED]', 'Accept':'application/json'}
