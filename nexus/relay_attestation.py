"""Challenge-bound relay configuration proof (not a host isolation proof)."""
import hashlib
import hmac
import json
import secrets
from urllib.parse import urlsplit


def fingerprint(target: str) -> str:
    if not isinstance(target, str):
        raise ValueError('Invalid upstream target')
    u = urlsplit(target)
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.fragment or u.port not in (None, 443):
        raise ValueError('Invalid upstream target')
    return hashlib.sha256(target.encode('utf-8')).hexdigest()


def new_challenge() -> str:
    return secrets.token_hex(32)


def proof(secret: str, challenge: str, target: str) -> dict:
    if not isinstance(challenge, str) or len(challenge) != 64 or any(c not in '0123456789abcdef' for c in challenge):
        raise ValueError('Invalid challenge')
    digest = fingerprint(target)
    signature = hmac.new(secret.encode('ascii'), f'kaliv-relay-v1:{challenge}:{digest}'.encode('ascii'), hashlib.sha256).hexdigest()
    return {'version': 1, 'challenge': challenge, 'upstream_sha256': digest, 'signature': signature}


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate attestation field')
        result[key] = value
    return result


def verify(secret: str, challenge: str, target: str, response: bytes) -> None:
    if not isinstance(response, bytes) or len(response) > 4096:
        raise PermissionError('Relay attestation rejected')
    try:
        parsed = json.loads(response, object_pairs_hook=_unique_fields,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid constant')))
        expected = proof(secret, challenge, target)
        if not isinstance(parsed, dict) or set(parsed) != set(expected):
            raise ValueError('Invalid response')
        if type(parsed['version']) is not int or parsed['version'] != 1 or not all(isinstance(parsed[k], str) for k in ('challenge', 'upstream_sha256', 'signature')):
            raise ValueError('Invalid response')
        if any(not hmac.compare_digest(parsed[k], expected[k]) for k in ('challenge', 'upstream_sha256', 'signature')):
            raise ValueError('Mismatched proof')
    except (ValueError, TypeError, UnicodeError):
        raise PermissionError('Relay attestation rejected') from None
