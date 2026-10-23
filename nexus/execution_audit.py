"""Append-only audit of execution planning. Never performs network I/O."""
import hashlib
import json


def record_plan(db, digest: str, operation_id: str, parameters: dict, outcome: str, reason: str = ''):
    # Never persist parameter values (they may contain identifiers or secrets).
    parameter_keys = sorted(str(key) for key in parameters) if isinstance(parameters, dict) else []
    fingerprint = hashlib.sha256(json.dumps(parameter_keys, separators=(',', ':')).encode()).hexdigest()
    db.execute('''INSERT INTO execution_plan_events
        (spec_digest, operation_id, parameter_keys_sha256, outcome, reason)
        VALUES (?, ?, ?, ?, ?)''', (digest, operation_id, fingerprint, outcome, reason[:160]))


def history(db, digest: str, operation_id: str, limit: int = 100):
    return [dict(row) for row in db.execute('''SELECT id, outcome, reason, occurred_at
        FROM execution_plan_events WHERE spec_digest=? AND operation_id=?
        ORDER BY id DESC LIMIT ?''', (digest, operation_id, limit))]
