"""Explicit credential-to-connection scoping; no secret values persisted."""
from dataclasses import dataclass
from urllib.parse import urlsplit
import hmac

from nexus.credentials import CredentialBinding


@dataclass(frozen=True)
class CredentialScope:
    binding: CredentialBinding
    endpoint: str
    allowed_methods: tuple[str, ...] = ('initialize', 'notifications/initialized', 'tools/list')

    def __post_init__(self):
        p = urlsplit(self.endpoint)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.fragment or p.port not in (None, 443):
            raise ValueError('Invalid credential scope endpoint')
        if not self.allowed_methods or any(not isinstance(m, str) or not m for m in self.allowed_methods):
            raise ValueError('Invalid allowed methods')

    def authorize(self, connection_name: str, url: str, method: str) -> None:
        if not hmac.compare_digest(connection_name, self.binding.connection_name):
            raise PermissionError('Credential scope denied')
        if not hmac.compare_digest(url, self.endpoint):
            raise PermissionError('Credential scope denied')
        if method not in self.allowed_methods:
            raise PermissionError('Credential scope denied')
