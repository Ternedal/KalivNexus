"""Explicit, local reviewer authorization boundary.

This module never activates a provider. Identity is supplied by a trusted caller;
it is NOT inferred from user-controlled review text.
"""
from dataclasses import dataclass
from typing import FrozenSet

from scripts.persistent_registry import PersistentManifestRegistry


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    subject: str
    roles: FrozenSet[str]
    issuer: str

    def __post_init__(self):
        if not self.subject.strip() or not self.issuer.strip():
            raise ValueError("Authenticated principal requires subject and issuer")


class ReviewService:
    def __init__(self, registry: PersistentManifestRegistry, trusted_issuer: str):
        if not trusted_issuer:
            raise ValueError("Trusted issuer is required")
        self._registry = registry
        self._trusted_issuer = trusted_issuer

    def submit_review(self, identifier: str, principal: AuthenticatedPrincipal,
                      decision: str, reason: str) -> None:
        if not isinstance(principal, AuthenticatedPrincipal):
            raise PermissionError("An authenticated principal is required")
        if principal.issuer != self._trusted_issuer:
            raise PermissionError("Untrusted identity issuer")
        if "nexus:reviewer" not in principal.roles:
            raise PermissionError("Reviewer role is required")
        self._registry.record_review(identifier, principal.subject, decision, reason)
