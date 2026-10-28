"""Opt-in MCP bearer authentication via runtime-only secret resolution."""
import os
import json
from nexus.credential_policy import CredentialScope
from nexus.credentials import CredentialBinding, bearer_headers
from nexus.mcp_network import MCPNetworkTransport


def environment_secret_provider(ref: str) -> str:
    """Read an explicitly named environment variable at call time; never persist it."""
    value = os.environ.get(ref)
    if value is None:
        raise PermissionError('Credential unavailable')
    return value


class AuthenticatedMCPTransport(MCPNetworkTransport):
    def __init__(self, url, *, binding: CredentialBinding, secret_provider=environment_secret_provider, scope: CredentialScope | None = None, **kwargs):
        if not isinstance(binding, CredentialBinding):
            raise ValueError('Credential binding required')
        if not isinstance(scope, CredentialScope):
            raise PermissionError('Credential scope required')
        if scope.binding != binding or scope.endpoint != url:
            raise PermissionError('Credential scope denied')
        super().__init__(url, **kwargs)
        self._scope = scope
        self._credential_binding = binding
        self._secret_provider = secret_provider

    def _auth_headers(self):
        return bearer_headers(self._credential_binding, self._secret_provider)

    def _post(self, payload):
        try:
                message = json.loads(payload)
                method = message.get('method')
        except (ValueError, TypeError, AttributeError):
            raise PermissionError('Credential scope denied') from None
        if not isinstance(method, str):
            raise PermissionError('Credential scope denied')
        self._scope.authorize(self._credential_binding.connection_name, self.url, method)
        return super()._post(payload)
