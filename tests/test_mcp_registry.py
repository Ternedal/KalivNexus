import sqlite3
import pytest
from nexus.mcp_registry import register_manifest, change_tool_status, list_mcp_tools


def db():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.executescript('''
      CREATE TABLE mcp_manifests(digest TEXT PRIMARY KEY,document TEXT,created_at TEXT);
      CREATE TABLE mcp_tools(manifest_digest TEXT,name TEXT,description TEXT,input_schema TEXT,status TEXT,PRIMARY KEY(manifest_digest,name));
      CREATE TABLE mcp_tool_reviews(id INTEGER PRIMARY KEY,manifest_digest TEXT,name TEXT,previous_status TEXT,new_status TEXT,reason TEXT,occurred_at TEXT);
    ''')
    return conn


def test_versioned_registry_and_review():
    conn = db()
    manifest = {'tools': [{'name':'weather.lookup','inputSchema':{'type':'object'}}]}
    a = register_manifest(conn, manifest)
    assert register_manifest(conn, manifest)['digest'] == a['digest']
    assert not list_mcp_tools(conn)
    change_tool_status(conn,a['digest'],'weather.lookup','reviewed','Reviewed manually')
    change_tool_status(conn,a['digest'],'weather.lookup','approved','Approved manually')
    assert len(list_mcp_tools(conn)) == 1
    assert list_mcp_tools(conn)[0]['executable'] is False
    assert conn.execute('SELECT COUNT(*) FROM mcp_tool_reviews').fetchone()[0] == 2
    changed = {'tools': [{'name':'weather.lookup','description':'changed','inputSchema':{'type':'object'}}]}
    b = register_manifest(conn, changed)
    assert b['digest'] != a['digest']
    assert len(list_mcp_tools(conn)) == 1


def test_invalid_transition_and_missing_tool():
    conn = db()
    digest = register_manifest(conn, {'tools':[{'name':'a'}]})['digest']
    with pytest.raises(ValueError):
        change_tool_status(conn,digest,'a','approved','Skip review')
    with pytest.raises(LookupError):
        change_tool_status(conn,digest,'missing','reviewed','Valid reason')
