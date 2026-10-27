"""Regression for Codex P2 4394998215 on #39: a path parameter must not leave the approved route.

quote(value, safe='') leaves '.' unencoded, so {"item": ".."} on an approved
/public/{item}/status produced /public/../status, which a normalizing upstream
serves as /status -- a route nobody approved. The opt-in executor dereferences
the planned target, and its egress checks restrict the host, not the path.
"""
import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("NEXUS_ADMIN_TOKEN", "test-secret")

import nexus.db as storage  # noqa: E402
from nexus.db import connect  # noqa: E402
from nexus.gateway import plan  # noqa: E402
from nexus.registry import register, transition  # noqa: E402

DOCUMENT = {"openapi": "3.0.3", "servers": [{"url": "https://example.com"}],
            "paths": {"/public/{item}/status": {"get": {"summary": "Read item status"}}}}


@pytest.fixture
def approved(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "nexus.db")
    with connect() as db:
        digest = register(db, DOCUMENT)["digest"]
        op = db.execute("SELECT operation_id FROM api_operations").fetchone()[0]
        transition(db, digest, op, "reviewed", "Reviewed manually")
        transition(db, digest, op, "approved", "Approved manually")
    return digest, op


@pytest.mark.parametrize("value", ["..", "."])
def test_dot_segments_are_rejected(approved, value):
    digest, op = approved
    with connect() as db, pytest.raises(ValueError, match="dot segment"):
        plan(db, digest, op, {"item": value})


@pytest.mark.parametrize("value, segment", [
    ("...", "..."),            # not an RFC 3986 dot segment
    ("a..b", "a..b"),
    (".hidden", ".hidden"),
    ("../x", "..%2Fx"),        # the slash is encoded, so this stays one segment
    ("%2e%2e", "%252e%252e"),  # percent signs are encoded, so no decoding to '..'
])
def test_other_values_stay_inside_one_segment(approved, value, segment):
    digest, op = approved
    with connect() as db:
        target = plan(db, digest, op, {"item": value})["target_url"]
    assert target == f"https://example.com/public/{segment}/status"


def test_opt_in_execution_never_sends_a_dot_segment(approved, monkeypatch):
    import nexus.isolated
    import nexus.main as main

    calls = []
    monkeypatch.setattr(main, "TOKEN", "test-secret")
    monkeypatch.setenv("NEXUS_ENABLE_HTTP_EXECUTION", "true")
    monkeypatch.setattr(nexus.isolated, "execute_isolated", lambda url: calls.append(url) or {"status_code": 200})
    digest, op = approved
    with TestClient(main.app) as client:
        response = client.post(f"/v1/specs/{digest}/operations/{op}/execute", json={"parameters": {"item": ".."}},
                               headers={"Authorization": "Bearer test-secret"})
    assert response.status_code != 200
    assert calls == []
