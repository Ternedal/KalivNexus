"""Persistent, auditable manual review state transitions."""
import json
import sqlite3
from datetime import datetime, timezone

ALLOWED = {
    'discovered': {'reviewed', 'disabled'},
    'reviewed': {'approved', 'disabled'},
    'approved': {'disabled'},
    'disabled': {'reviewed'},
}


def change_status(db: sqlite3.Connection, capability_id: str, target: str, reason: str, actor: str = 'admin') -> dict:
    row = db.execute('SELECT status FROM capabilities WHERE id=?', (capability_id,)).fetchone()
    if row is None:
        raise LookupError('Capability not found')
    current = row['status']
    if target not in ALLOWED[current]:
        raise ValueError(f'Invalid transition: {current} -> {target}')
    if not reason.strip() or len(reason.strip()) < 5:
        raise ValueError('A review reason of at least 5 characters is required')
    now = datetime.now(timezone.utc).isoformat()
    db.execute('UPDATE capabilities SET status=?, updated_at=? WHERE id=?', (target, now, capability_id))
    db.execute('INSERT INTO review_events (capability_id, previous_status, new_status, reason, actor, occurred_at) VALUES (?,?,?,?,?,?)',
               (capability_id, current, target, reason.strip(), actor, now))
    return {'id': capability_id, 'previous_status': current, 'status': target, 'occurred_at': now}
