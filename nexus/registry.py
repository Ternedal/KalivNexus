"""Immutable OpenAPI snapshots and separately reviewed operations. No execution."""
import hashlib
import json
from datetime import datetime, timezone
from nexus.openapi import extract_operations
from nexus.policy import assess_operation

TRANSITIONS = {'discovered': {'reviewed', 'disabled'}, 'reviewed': {'approved', 'disabled'}, 'approved': {'disabled'}, 'disabled': {'reviewed'}}

def register(db, document):
    operations = extract_operations(document)
    if len(json.dumps(document).encode('utf-8')) > 1_000_000:
        raise ValueError('Document exceeds 1 MB')
    canonical = json.dumps(document, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    exists = db.execute('SELECT 1 FROM api_specs WHERE digest=?', (digest,)).fetchone()
    if not exists:
        db.execute('INSERT INTO api_specs (digest, document, created_at) VALUES (?,?,?)', (digest, canonical, datetime.now(timezone.utc).isoformat()))
        for op in operations:
            op.update(assess_operation(op, document))
            db.execute('INSERT INTO api_operations (spec_digest, operation_id, method, path, name, risk_level, risk_flags, status) VALUES (?,?,?,?,?,?,?,?)',
                       (digest, op['id'], op['method'], op['path'], op['name'], op['risk_level'], json.dumps(op['risk_flags']), 'discovered'))
    return {'digest': digest, 'created': not bool(exists), 'operation_count': len(operations), 'executable': False}

def transition(db, digest, operation_id, target, reason):
    if len(reason.strip()) < 5:
        raise ValueError('Reason must contain at least 5 characters')
    row = db.execute('SELECT status FROM api_operations WHERE spec_digest=? AND operation_id=?', (digest, operation_id)).fetchone()
    if not row:
        raise LookupError('Operation not found')
    current = row['status']
    if target not in TRANSITIONS[current]:
        raise ValueError(f'Invalid transition: {current} -> {target}')
    now = datetime.now(timezone.utc).isoformat()
    db.execute('UPDATE api_operations SET status=? WHERE spec_digest=? AND operation_id=?', (target, digest, operation_id))
    db.execute('INSERT INTO operation_review_events (spec_digest, operation_id, previous_status, new_status, reason, occurred_at) VALUES (?,?,?,?,?,?)',
               (digest, operation_id, current, target, reason.strip(), now))
    return {'digest': digest, 'operation_id': operation_id, 'previous_status': current, 'status': target, 'executable': False}
