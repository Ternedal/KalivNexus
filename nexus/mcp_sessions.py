"""Persistent, offline MCP session lifecycle. No network connections or tool calls."""
import secrets
from datetime import datetime, timedelta, timezone

STATES = {'created', 'initializing', 'initialized', 'ready', 'closed', 'expired'}
TRANSITIONS = {
    'created': {'initializing'},
    'initializing': {'initialized', 'closed'},
    'initialized': {'ready', 'closed'},
    'ready': {'closed'},
}
MAX_TTL = 3600

def utcnow():
    return datetime.now(timezone.utc)

def create_session(db, connection_name: str, ttl_seconds: int = 300) -> dict:
    if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or not 1 <= ttl_seconds <= MAX_TTL:
        raise ValueError('TTL must be between 1 and 3600 seconds')
    if not db.execute('SELECT 1 FROM mcp_connections WHERE name=?', (connection_name,)).fetchone():
        raise KeyError('Unknown connection')
    session_id = secrets.token_urlsafe(32)
    now = utcnow()
    expiry = now + timedelta(seconds=ttl_seconds)
    db.execute('INSERT INTO mcp_sessions(id,connection_name,state,created_at,expires_at) VALUES(?,?,?,?,?)',
               (session_id, connection_name, 'created', now.isoformat(), expiry.isoformat()))
    return {'id': session_id, 'connection_name': connection_name, 'state': 'created', 'expires_at': expiry.isoformat(), 'executable': False}

def get_session(db, session_id: str) -> dict:
    row = db.execute('SELECT id,connection_name,state,expires_at FROM mcp_sessions WHERE id=?', (session_id,)).fetchone()
    if row is None:
        raise KeyError('Unknown session')
    result = dict(row)
    if result['state'] not in {'closed', 'expired'} and utcnow() >= datetime.fromisoformat(result['expires_at']):
        db.execute('UPDATE mcp_sessions SET state=? WHERE id=?', ('expired', session_id))
        result['state'] = 'expired'
    result['executable'] = False
    return result

def transition_session(db, session_id: str, target: str) -> dict:
    session = get_session(db, session_id)
    if target not in TRANSITIONS.get(session['state'], set()):
        raise ValueError('Invalid session transition')
    db.execute('UPDATE mcp_sessions SET state=? WHERE id=?', (target, session_id))
    session['state'] = target
    return session
