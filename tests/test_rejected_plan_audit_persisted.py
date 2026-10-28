"""Regression for Codex P2 4394805160 on #39: rejected attempts must stay in the audit log.

nexus.db.connect() commits only after a normal return from its ``yield``.
plan_operation (and execute_operation's denial path) recorded the audit row
and then raised HTTPException inside ``with connect()``, so the row was rolled
back and /plan-events never showed rejected attempts.
"""
import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("NEXUS_ADMIN_TOKEN", "test-secret")

import nexus.db as storage  # noqa: E402
from nexus.db import connect  # noqa: E402
from nexus.registry import register, transition  # noqa: E402

HEADERS = {"Authorization": "Bearer test-secret"}
DOCUMENT = {"openapi": "3.0.3", "servers": [{"url": "https://example.com"}],
            "paths": {"/items/{item}": {"get": {"summary": "Read item"}}}}


@pytest.fixture
def client(tmp_path, monkeypatch):
    import nexus.main as main

    monkeypatch.setattr(storage, "DB_PATH", tmp_path / "nexus.db")
    monkeypatch.setattr(main, "TOKEN", "test-secret")
    with TestClient(main.app) as test_client:
        yield test_client


def _operation(approved: bool):
    with connect() as db:
        digest = register(db, DOCUMENT)["digest"]
        op = db.execute("SELECT operation_id FROM api_operations").fetchone()[0]
        if approved:
            transition(db, digest, op, "reviewed", "Reviewed manually")
            transition(db, digest, op, "approved", "Approved manually")
    return digest, op


def _events(client, digest, op):
    response = client.get(f"/v1/specs/{digest}/operations/{op}/plan-events", headers=HEADERS)
    assert response.status_code == 200, response.text
    return [(e["outcome"], e["reason"]) for e in response.json()]


def test_unapproved_plan_is_rejected_and_audited(client):
    digest, op = _operation(approved=False)
    response = client.post(f"/v1/specs/{digest}/operations/{op}/plan", json={"parameters": {"item": "a"}},
                           headers=HEADERS)
    assert response.status_code == 403
    assert _events(client, digest, op) == [("denied", "PermissionError")]


def test_invalid_and_missing_plans_are_audited(client):
    digest, op = _operation(approved=True)
    bad = client.post(f"/v1/specs/{digest}/operations/{op}/plan", json={"parameters": {"other": "x"}},
                      headers=HEADERS)
    assert bad.status_code == 422
    missing = client.post(f"/v1/specs/{digest}/operations/noSuchOp/plan", json={"parameters": {}}, headers=HEADERS)
    assert missing.status_code == 404
    assert _events(client, digest, op) == [("invalid", "ValueError")]
    assert _events(client, digest, "noSuchOp") == [("missing", "LookupError")]


def test_allowed_plan_is_still_audited(client):
    digest, op = _operation(approved=True)
    ok = client.post(f"/v1/specs/{digest}/operations/{op}/plan", json={"parameters": {"item": "a"}}, headers=HEADERS)
    assert ok.status_code == 200
    assert _events(client, digest, op) == [("allowed", "")]


def test_denied_execution_is_audited(client, monkeypatch):
    import nexus.isolated

    def refuse(url):
        raise RuntimeError("upstream refused")

    monkeypatch.setenv("NEXUS_ENABLE_HTTP_EXECUTION", "true")
    monkeypatch.setattr(nexus.isolated, "execute_isolated", refuse)
    digest, op = _operation(approved=True)
    response = client.post(f"/v1/specs/{digest}/operations/{op}/execute", json={"parameters": {"item": "a"}},
                           headers=HEADERS)
    assert response.status_code == 502
    assert _events(client, digest, op) == [("execution_denied", "RuntimeError")]
