import sqlite3
import pytest
from nexus.mcp_reconcile import reconcile_discovery
from nexus.mcp_registry import register_manifest, change_tool_status
from nexus.mcp_connections import register_connection
from nexus.mcp_sessions import create_session, transition_session


def setup():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript('''
    CREATE TABLE mcp_manifests(digest TEXT PRIMARY KEY,document TEXT,created_at TEXT);
    CREATE TABLE mcp_tools(manifest_digest TEXT,name TEXT,description TEXT,input_schema TEXT,status TEXT,PRIMARY KEY(manifest_digest,name));
    CREATE TABLE mcp_tool_reviews(manifest_digest TEXT,name TEXT,previous_status TEXT,new_status TEXT,reason TEXT,occurred_at TEXT);
    CREATE TABLE mcp_connections(name TEXT PRIMARY KEY,url TEXT,manifest_digest TEXT,enabled INTEGER);
    CREATE TABLE mcp_sessions(id TEXT PRIMARY KEY,connection_name TEXT,state TEXT,created_at TEXT,expires_at TEXT);
    ''')
    tool = {'name':'weather','description':'Read forecast','inputSchema':{'type':'object','properties':{}}}
    digest = register_manifest(db, {'tools':[tool]})['digest']
    register_connection(db,'weather','https://api.example.com/mcp',digest)
    sid = create_session(db,'weather')['id']
    for state in ('initializing','initialized','ready'):
        transition_session(db,sid,state)
    return db,sid,tool,digest


def discovery(tools):
    return {'tools':tools,'count':len(tools),'executable':False,'approved':False}


def test_exact_match_and_approval():
    db,sid,tool,digest=setup()
    change_tool_status(db,digest,'weather','reviewed','Reviewed for testing')
    change_tool_status(db,digest,'weather','approved','Approved for testing')
    result=reconcile_discovery(db,sid,discovery([tool]))
    assert result['manifest_matches']
    assert result['approved_matching_tools']==['weather']
    assert result['execution_allowed'] is False


def test_changed_schema_revokes_match():
    db,sid,tool,_=setup()
    tool['inputSchema']={'type':'object','properties':{'secret':{'type':'string'}}}
    result=reconcile_discovery(db,sid,discovery([tool]))
    assert result['changed']==['weather']
    assert not result['manifest_matches']
    assert result['approved_matching_tools']==[]


def test_added_tool_revokes_manifest_match():
    db,sid,tool,_=setup()
    other={'name':'other','description':'Other','inputSchema':{'type':'object'}}
    result=reconcile_discovery(db,sid,discovery([tool,other]))
    assert result['added']==['other']
    assert not result['manifest_matches']


def test_not_ready_denied():
    db,sid,tool,_=setup()
    transition_session(db,sid,'closed')
    with pytest.raises(ValueError,match='ready'):
        reconcile_discovery(db,sid,discovery([tool]))


def test_untrusted_discovery_flags_denied():
    db,sid,tool,_=setup()
    with pytest.raises(ValueError):
        reconcile_discovery(db,sid,{'tools':[tool],'count':1,'executable':True,'approved':False})
