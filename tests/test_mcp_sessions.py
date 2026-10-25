import sqlite3
import pytest
from nexus.mcp_sessions import create_session, get_session, transition_session

@pytest.fixture
def db():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE mcp_connections(name TEXT PRIMARY KEY)')
    db.execute("INSERT INTO mcp_connections VALUES ('demo')")
    db.execute('CREATE TABLE mcp_sessions(id TEXT PRIMARY KEY, connection_name TEXT, state TEXT, created_at TEXT, expires_at TEXT)')
    yield db
    db.close()

def test_lifecycle(db):
    session = create_session(db, 'demo')
    assert not session['executable']
    for state in ['initializing', 'initialized', 'ready', 'closed']:
        assert transition_session(db, session['id'], state)['state'] == state

def test_invalid_transition(db):
    sid = create_session(db, 'demo')['id']
    with pytest.raises(ValueError):
        transition_session(db, sid, 'ready')

def test_missing_connection(db):
    with pytest.raises(KeyError):
        create_session(db, 'missing')

def test_ttl_limits(db):
    for ttl in (0, 3601, True):
        with pytest.raises(ValueError):
            create_session(db, 'demo', ttl)

def test_expired(db):
    sid = create_session(db, 'demo')['id']
    db.execute("UPDATE mcp_sessions SET expires_at='2000-01-01T00:00:00+00:00' WHERE id=?", (sid,))
    assert get_session(db, sid)['state'] == 'expired'
    with pytest.raises(ValueError):
        transition_session(db, sid, 'initializing')

def test_unknown_session(db):
    with pytest.raises(KeyError):
        get_session(db, 'not-found')
