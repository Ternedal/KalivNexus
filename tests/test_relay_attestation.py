import json
import pytest
from nexus.relay_attestation import proof, verify, new_challenge, fingerprint
from nexus.mcp_relay_client import MCPRelayTransport

SECRET = 's' * 40
URL = 'https://mcp.example.org/mcp'

def test_proof_roundtrip():
    challenge = new_challenge()
    verify(SECRET, challenge, URL, json.dumps(proof(SECRET, challenge, URL)).encode())

def test_wrong_upstream_denied():
    challenge = new_challenge()
    with pytest.raises(PermissionError):
        verify(SECRET, challenge, 'https://other.example.org/mcp', json.dumps(proof(SECRET, challenge, URL)).encode())

def test_replayed_challenge_denied():
    first, second = new_challenge(), new_challenge()
    with pytest.raises(PermissionError):
        verify(SECRET, second, URL, json.dumps(proof(SECRET, first, URL)).encode())

def test_wrong_secret_denied():
    challenge = new_challenge()
    with pytest.raises(PermissionError):
        verify('z' * 40, challenge, URL, json.dumps(proof(SECRET, challenge, URL)).encode())

def test_bad_challenge_and_target():
    with pytest.raises(ValueError):
        proof(SECRET, 'short', URL)
    with pytest.raises(ValueError):
        fingerprint('http://localhost')

def test_oversized_or_malformed_denied():
    challenge = new_challenge()
    for body in (b'{' , b'X' * 4097, b'[]'):
        with pytest.raises(PermissionError):
            verify(SECRET, challenge, URL, body)

def test_relay_client_attest():
    class Response:
        status = 200
        def getheader(self, key): return 'application/json' if key == 'Content-Type' else None
        def read(self, n): return self.payload
    class Connection:
        def __init__(self, host, port, timeout): assert host == 'relay' and port == 8787
        def request(self, method, path, headers):
            assert (method, path) == ('GET', '/attest')
            self.challenge = headers['X-Nexus-Challenge']
        def getresponse(self):
            r = Response()
            r.payload = json.dumps(proof(SECRET, self.challenge, URL)).encode()
            return r
        def close(self): pass
    MCPRelayTransport(host='relay', secret=SECRET, enabled=True, connection_factory=Connection).attest(URL)


def test_duplicate_attestation_keys_rejected():
    challenge = new_challenge()
    valid = json.dumps(proof(SECRET, challenge, URL))
    duplicated = valid[:-1] + ',"signature":"' + '0' * 64 + '"}'
    with pytest.raises(PermissionError):
        verify(SECRET, challenge, URL, duplicated.encode())

def test_attestation_rejects_nonstandard_json_constants():
    challenge = new_challenge()
    body = json.dumps(proof(SECRET, challenge, URL)).replace('"version": 1', '"version": NaN')
    with pytest.raises(PermissionError):
        verify(SECRET, challenge, URL, body.encode())

@pytest.mark.parametrize('header', ['4097', '-1', 'nan', '999999999999999999999'])
def test_attestation_rejects_invalid_length_before_read(header):
    class Response:
        status = 200
        def getheader(self, key):
            return 'application/json' if key == 'Content-Type' else header
        def read(self, limit):
            raise AssertionError('Must reject before reading response body')
    class Connection:
        def __init__(self, *args, **kwargs): pass
        def request(self, *args, **kwargs): pass
        def getresponse(self): return Response()
        def close(self): pass
    client = MCPRelayTransport(host='relay', secret=SECRET, enabled=True, connection_factory=Connection)
    with pytest.raises(PermissionError):
        client.attest(URL)


def test_boolean_version_rejected_even_when_signature_valid():
    challenge = new_challenge()
    response = proof(SECRET, challenge, URL)
    response['version'] = True  # Python True == 1, but JSON true is not protocol version 1
    with pytest.raises(PermissionError):
        verify(SECRET, challenge, URL, json.dumps(response).encode())


def test_attestation_rejects_wrong_version_type():
    challenge = new_challenge()
    for version in ('1', 1.0, None):
        response = proof(SECRET, challenge, URL)
        response['version'] = version
        with pytest.raises(PermissionError):
            verify(SECRET, challenge, URL, json.dumps(response).encode())
