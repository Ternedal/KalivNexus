import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.environ.get("NEXUS_DB", "./data/nexus.db"))

@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS capabilities (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL,
            category TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'discovered',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_capability_category ON capabilities(category)")
        db.execute("""CREATE TABLE IF NOT EXISTS review_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            capability_id TEXT NOT NULL,
            previous_status TEXT NOT NULL,
            new_status TEXT NOT NULL,
            reason TEXT NOT NULL,
            actor TEXT NOT NULL,
            occurred_at TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_review_events_capability ON review_events(capability_id, id)")
        db.execute("""CREATE TABLE IF NOT EXISTS api_specs (
            digest TEXT PRIMARY KEY, document TEXT NOT NULL, created_at TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS api_operations (
            spec_digest TEXT NOT NULL, operation_id TEXT NOT NULL,
            method TEXT NOT NULL, path TEXT NOT NULL, name TEXT NOT NULL,
            risk_level TEXT NOT NULL, risk_flags TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'discovered',
            PRIMARY KEY (spec_digest, operation_id),
            FOREIGN KEY (spec_digest) REFERENCES api_specs(digest))""")
        db.execute("""CREATE TABLE IF NOT EXISTS operation_review_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, spec_digest TEXT NOT NULL,
            operation_id TEXT NOT NULL, previous_status TEXT NOT NULL,
            new_status TEXT NOT NULL, reason TEXT NOT NULL, occurred_at TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS execution_plan_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            spec_digest TEXT NOT NULL,
            operation_id TEXT NOT NULL,
            parameter_keys_sha256 TEXT NOT NULL,
            outcome TEXT NOT NULL CHECK(outcome IN ('allowed', 'denied', 'invalid', 'missing')),
            reason TEXT NOT NULL DEFAULT '',
            occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_plan_events_operation ON execution_plan_events(spec_digest, operation_id, id)")
        db.execute("""CREATE TABLE IF NOT EXISTS mcp_manifests (
            digest TEXT PRIMARY KEY, document TEXT NOT NULL, created_at TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS mcp_tools (
            manifest_digest TEXT NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL,
            input_schema TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'discovered',
            PRIMARY KEY(manifest_digest,name))""")
        db.execute("""CREATE TABLE IF NOT EXISTS mcp_tool_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT, manifest_digest TEXT NOT NULL,
            name TEXT NOT NULL, previous_status TEXT NOT NULL, new_status TEXT NOT NULL,
            reason TEXT NOT NULL, occurred_at TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS mcp_connections (
            name TEXT PRIMARY KEY, url TEXT NOT NULL, manifest_digest TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled=0))""")
        db.execute("""CREATE TABLE IF NOT EXISTS mcp_sessions (
            id TEXT PRIMARY KEY, connection_name TEXT NOT NULL,
            state TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
            FOREIGN KEY(connection_name) REFERENCES mcp_connections(name))""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_mcp_sessions_connection ON mcp_sessions(connection_name)")
        db.commit()
        yield db
        db.commit()
    finally:
        db.close()
