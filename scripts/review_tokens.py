"""Verify short-lived HMAC-SHA256 review tokens before reaching ReviewService.

A trusted issuer must hold the shared secret. Tokens are not an OIDC substitute.
"""
import base64
import hashlib
import hmac
import json
import re
import time
from typing import Callable

from scripts.review_authorization import AuthenticatedPrincipal, ReviewService


def _decode(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


class ReviewTokenVerifier:
    def __init__(self, secret: bytes, issuer: str, audience: str,
                 clock: Callable[[], float] = time.time):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("Token signing key must contain at least 32 bytes")
        if not issuer or not audience:
            raise ValueError("Issuer and audience are required")
        self._secret = secret
        self._issuer = issuer
        self._audience = audience
        self._clock = clock

    def verify(self, token: str) -> AuthenticatedPrincipal:
        if not isinstance(token, str) or len(token) > 8192:
            raise PermissionError("Invalid token")
        try:
            payload_part, signature_part = token.split(".")
            supplied = _decode(signature_part)
            expected = hmac.new(self._secret, payload_part.encode("ascii"), hashlib.sha256).digest()
            if not hmac.compare_digest(supplied, expected):
                raise PermissionError("Invalid signature")
            claims = json.loads(_decode(payload_part))
            if not isinstance(claims, dict):
                raise PermissionError("Invalid claims")
            now = int(self._clock())
            issued = claims["iat"]
            expiry = claims["exp"]
            if type(issued) is not int or type(expiry) is not int:
                raise PermissionError("Invalid timestamps")
            if issued > now + 30 or expiry <= now or expiry <= issued or expiry - issued > 300:
                raise PermissionError("Token outside allowed lifetime")
            if claims["iss"] != self._issuer or claims["aud"] != self._audience:
                raise PermissionError("Issuer or audience mismatch")
            nonce = claims["jti"]
            if not isinstance(nonce, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", nonce):
                raise PermissionError("Invalid token identifier")
            roles = claims["roles"]
            if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
                raise PermissionError("Invalid roles")
            subject = claims["sub"]
            if not isinstance(subject, str) or not subject.strip():
                raise PermissionError("Invalid subject")
            return AuthenticatedPrincipal(subject=subject, issuer=self._issuer, roles=frozenset(roles))
        except (ValueError, KeyError, TypeError, UnicodeError) as exc:
            raise PermissionError("Malformed review token") from exc


class SignedReviewService:
    def __init__(self, service: ReviewService, verifier: ReviewTokenVerifier):
        self._service = service
        self._verifier = verifier

    def submit_review(self, identifier: str, token: str, decision: str, reason: str) -> None:
        principal = self._verifier.verify(token)
        claims = json.loads(_decode(token.split(".")[0]))
        nonce = claims["jti"]
        # Unique SQLite key prevents replay across processes and restarts.
        # Fail closed: reservation remains consumed even if review submission fails.
        self._service._registry.consume_review_token(principal.issuer, nonce, claims["exp"])
        self._service.submit_review(identifier, principal, decision, reason)
