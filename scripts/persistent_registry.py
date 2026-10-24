"""SQLite-backed default-deny catalog with append-only lifecycle events.

No provider invocation, activation, credentials, or network operations.
"""
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from scripts.validate_manifest import validate_manifest


class PersistentManifestRegistry:
    def __init__(self, database: str | Path):
        self.database = str(database)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.database, timeout=10)
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS capabilities (
                capability_id TEXT PRIMARY KEY,
                manifest_json TEXT NOT NULL,
                manifest_sha256 TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('disabled', 'revoked'))
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS lifecycle_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                capability_id TEXT NOT NULL REFERENCES capabilities(capability_id),
                action TEXT NOT NULL CHECK(action IN ('registered', 'revoked')),
                reason TEXT NOT NULL,
                manifest_sha256 TEXT NOT NULL,
                occurred_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS review_events (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                capability_id TEXT NOT NULL REFERENCES capabilities(capability_id),
                reviewer TEXT NOT NULL,
                decision TEXT NOT NULL CHECK(decision IN ('approved','rejected')),
                reason TEXT NOT NULL,
                manifest_sha256 TEXT NOT NULL,
                occurred_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            )""")

    def register(self, manifest: dict[str, Any], reason: str = "initial registration") -> str:
        validate_manifest(manifest)
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("A nonempty audit reason is required")
        serialized = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        identifier = manifest["capability_id"]
        with self._connect() as db:
            db.execute("INSERT INTO capabilities VALUES (?, ?, ?, 'disabled')", (identifier, serialized, digest))
            db.execute(
                "INSERT INTO lifecycle_events (capability_id, action, reason, manifest_sha256) VALUES (?, 'registered', ?, ?)",
                (identifier, reason, digest),
            )
        return identifier

    def register_file(self, path: str | Path, reason: str = "initial registration") -> str:
        return self.register(json.loads(Path(path).read_text(encoding="utf-8")), reason)

    def revoke(self, identifier: str, reason: str) -> None:
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("A nonempty revocation reason is required")
        with self._connect() as db:
            row = db.execute("SELECT status, manifest_sha256 FROM capabilities WHERE capability_id=?", (identifier,)).fetchone()
            if row is None:
                raise KeyError(identifier)
            if row[0] == "revoked":
                raise ValueError("Already revoked")
            db.execute("UPDATE capabilities SET status='revoked' WHERE capability_id=?", (identifier,))
            db.execute(
                "INSERT INTO lifecycle_events (capability_id, action, reason, manifest_sha256) VALUES (?, 'revoked', ?, ?)",
                (identifier, reason, row[1]),
            )

    def get(self, identifier: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT manifest_json, manifest_sha256, status FROM capabilities WHERE capability_id=?", (identifier,)).fetchone()
        if row is None:
            raise KeyError(identifier)
        return {"manifest": json.loads(row[0]), "manifest_sha256": row[1], "status": row[2]}

    def list_capabilities(self) -> list[dict[str, str]]:
        with self._connect() as db:
            rows = db.execute("SELECT capability_id, status FROM capabilities ORDER BY capability_id").fetchall()
        return [{"capability_id": identifier, "status": status} for identifier, status in rows]

    def audit_events(self, identifier: str) -> list[dict[str, Any]]:
        self.get(identifier)
        with self._connect() as db:
            rows = db.execute(
                "SELECT event_id, action, reason, manifest_sha256, occurred_at FROM lifecycle_events WHERE capability_id=? ORDER BY event_id",
                (identifier,),
            ).fetchall()
        return [
            dict(zip(("event_id", "action", "reason", "manifest_sha256", "occurred_at"), row))
            for row in rows
        ]

    def record_review(self, identifier: str, reviewer: str, decision: str, reason: str) -> None:
        """Record a human review without granting any runtime authority."""
        if decision not in ("approved", "rejected"):
            raise ValueError("Review decision must be approved or rejected")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError("Reviewer identity is required")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Review reason is required")
        with self._connect() as db:
            row = db.execute(
                "SELECT status, manifest_sha256 FROM capabilities WHERE capability_id=?", (identifier,)
            ).fetchone()
            if row is None:
                raise KeyError(identifier)
            if row[0] != "disabled":
                raise PermissionError("Revoked capability cannot be reviewed")
            db.execute(
                "INSERT INTO review_events (capability_id, reviewer, decision, reason, manifest_sha256) VALUES (?, ?, ?, ?, ?)",
                (identifier, reviewer, decision, reason, row[1]),
            )

    def review_events(self, identifier: str) -> list[dict[str, Any]]:
        self.get(identifier)
        with self._connect() as db:
            rows = db.execute(
                "SELECT review_id, reviewer, decision, reason, manifest_sha256, occurred_at FROM review_events WHERE capability_id=? ORDER BY review_id",
                (identifier,),
            ).fetchall()
        return [dict(zip(
            ("review_id", "reviewer", "decision", "reason", "manifest_sha256", "occurred_at"), row
        )) for row in rows]

    def execute(self, identifier: str, **kwargs: Any) -> None:
        raise PermissionError("Execution is disabled: no authorization/runtime adapter exists")
