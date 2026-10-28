"""Regression for Codex P1 4394805150 on #39: opt-in HTTP execution must be auditable.

nexus.main records 'executed' and 'execution_denied' for every execution
attempt, but the v0.50.0 CHECK on execution_plan_events allowed only the four
planning outcomes, so each insert raised sqlite3.IntegrityError and a
successful upstream GET came back as HTTP 500. The table now accepts both,
and a database created before the fix is migrated in place, keeping its rows.
"""
import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("NEXUS_ADMIN_TOKEN", "test-secret")

import nexus.db as storage  # noqa: E402
from nexus.db import PLAN_EVENT_OUTCOMES, connect  # noqa: E402
from nexus.execution_audit import history, record_plan  # noqa: E402
from nexus.registry import register, transition  # noqa: E402

OLD_DDL = """CREATE TABLE execution_plan_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spec_digest TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    parameter_keys_sha256 TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK(outcome IN ('allowed', 'denied', 'invalid', 'missing')),
    reason TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)"""


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "nexus.db"
    monkeypatch.setattr(storage, "DB_PATH", path)
    return path


def test_fresh_database_accepts_execution_outcomes(db_path):
    with connect() as db:
        for outcome in ("executed", "execution_denied"):
            record_plan(db, "d", "op", {}, outcome, "x")
        assert [r["outcome"] for r in history(db, "d", "op")] == ["execution_denied", "executed"]


def test_unknown_outcome_is_still_rejected(db_path):
    with connect() as db, pytest.raises(sqlite3.IntegrityError):
        record_plan(db, "d", "op", {}, "maybe")


def test_pre_fix_database_is_migrated_and_keeps_its_rows(db_path):
    legacy = sqlite3.connect(db_path)
    legacy.execute(OLD_DDL)
    legacy.execute("CREATE INDEX idx_plan_events_operation ON execution_plan_events(spec_digest, operation_id, id)")
    legacy.execute("INSERT INTO execution_plan_events (id, spec_digest, operation_id, parameter_keys_sha256, outcome,"
                   " reason, occurred_at) VALUES (7, 'd', 'op', 'h', 'denied', 'PermissionError', '2026-10-01T00:00:00')")
    legacy.commit()
    with pytest.raises(sqlite3.IntegrityError):
        legacy.execute("INSERT INTO execution_plan_events (spec_digest, operation_id, parameter_keys_sha256, outcome)"
                       " VALUES ('d', 'op', 'h', 'executed')")
    legacy.close()

    with connect() as db:
        rows = [dict(r) for r in db.execute("SELECT id, outcome, reason, occurred_at FROM execution_plan_events")]
        assert rows == [{"id": 7, "outcome": "denied", "reason": "PermissionError", "occurred_at": "2026-10-01T00:00:00"}]
        record_plan(db, "d", "op", {}, "executed", "200")
        newest = history(db, "d", "op", 1)[0]
        assert newest["outcome"] == "executed" and newest["id"] > 7
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "execution_plan_events_new" not in tables
        indexes = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert "idx_plan_events_operation" in indexes

    with connect() as db:  # idempotent: a second open does not rebuild or lose rows
        assert db.execute("SELECT COUNT(*) FROM execution_plan_events").fetchone()[0] == 2
        sql = db.execute("SELECT sql FROM sqlite_master WHERE name='execution_plan_events'").fetchone()[0]
        assert all(f"'{o}'" in sql for o in PLAN_EVENT_OUTCOMES)


def _approved_operation():
    document = {"openapi": "3.0.3", "servers": [{"url": "https://example.com"}],
                "paths": {"/items/{item}": {"get": {"summary": "Read item"}}}}
    with connect() as db:
        digest = register(db, document)["digest"]
        op = db.execute("SELECT operation_id FROM api_operations").fetchone()[0]
        transition(db, digest, op, "reviewed", "Reviewed manually")
        transition(db, digest, op, "approved", "Approved manually")
    return digest, op


def test_successful_opt_in_execution_returns_200_and_is_audited(db_path, monkeypatch):
    import nexus.isolated
    import nexus.main as main

    monkeypatch.setattr(main, "TOKEN", "test-secret")
    monkeypatch.setenv("NEXUS_ENABLE_HTTP_EXECUTION", "true")
    monkeypatch.setattr(nexus.isolated, "execute_isolated",
                        lambda url: {"status_code": 200, "content_type": "application/json", "body": "{}"})
    digest, op = _approved_operation()
    with TestClient(main.app) as client:
        headers = {"Authorization": "Bearer test-secret"}
        response = client.post(f"/v1/specs/{digest}/operations/{op}/execute", json={"parameters": {"item": "a"}},
                               headers=headers)
        assert response.status_code == 200, response.text
        events = client.get(f"/v1/specs/{digest}/operations/{op}/plan-events", headers=headers).json()
    assert [e["outcome"] for e in events][:1] == ["executed"]
