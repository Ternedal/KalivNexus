"""Credential references and redacted authorization headers.

Secrets are deliberately never persisted by this module. Production deployments
must inject them from a dedicated secret store at request time.
"""
import re
from dataclasses import dataclass

_REF = re.compile(r'^[A-Z][A-Z0-9_]{2,127}$')


def validate_secret_ref(ref: str) -> str:
    if not isinstance(ref, str) or not _REF.fullmatch(ref):
        raise ValueError('Invalid secret reference')
    return ref


@dataclass(frozen=True)
class CredentialBinding:
    connection_name: str
    secret_ref: str

    def __post_init__(self):
        if not isinstance(self.connection_name, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}', self.connection_name):
            raise ValueError('Invalid connection name')
        validate_secret_ref(self.secret_ref)


def bearer_headers(binding: CredentialBinding, secret_provider) -> dict:
    """Resolve only at execution time. Never include secret in logs or errors."""
    try:
        token = secret_provider(binding.secret_ref)
    except Exception:
        raise PermissionError('Credential unavailable') from None
    if not isinstance(token, str) or not token or len(token) > 8192 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise PermissionError('Credential unavailable')
    return {'Authorization': f'Bearer {token}'}


def redact_headers(headers: dict) -> dict:
    return {key: '[REDACTED]' if key.lower() in ('authorization', 'proxy-authorization', 'x-api-key', 'cookie', 'set-cookie') else value
            for key, value in headers.items()}
