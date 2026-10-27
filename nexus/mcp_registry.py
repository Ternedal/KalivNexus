"""Versioned, metadata-only MCP tool registry. Never executes MCP tools."""
import hashlib
import json
from datetime import datetime, timezone
from nexus.tools import normalize_mcp_manifest
from nexus.reviews import ALLOWED


def register_manifest(db, manifest: dict) -> dict:
    tools = normalize_mcp_manifest(manifest)
    canonical = json.dumps(tools, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    db.execute('INSERT OR IGNORE INTO mcp_manifests(digest,document,created_at) VALUES (?,?,?)', (digest, canonical, now))
    for tool in tools:
        db.execute('INSERT OR IGNORE INTO mcp_tools(manifest_digest,name,description,input_schema,status) VALUES (?,?,?,?,?)',
                   (digest, tool['name'], tool['description'], json.dumps(tool['input_schema'], sort_keys=True), 'discovered'))
    return {'digest': digest, 'count': len(tools), 'executable': False}


def change_tool_status(db, digest: str, name: str, target: str, reason: str) -> dict:
    row = db.execute('SELECT status FROM mcp_tools WHERE manifest_digest=? AND name=?', (digest, name)).fetchone()
    if row is None:
        raise LookupError('MCP tool not found')
    current = row['status']
    if target not in ALLOWED.get(current, set()):
        raise ValueError('Invalid status transition')
    if len(reason.strip()) < 5:
        raise ValueError('Reason must contain at least five characters')
    now = datetime.now(timezone.utc).isoformat()
    db.execute('UPDATE mcp_tools SET status=? WHERE manifest_digest=? AND name=?', (target, digest, name))
    db.execute('INSERT INTO mcp_tool_reviews(manifest_digest,name,previous_status,new_status,reason,occurred_at) VALUES (?,?,?,?,?,?)',
               (digest, name, current, target, reason.strip(), now))
    return {'digest': digest, 'name': name, 'previous_status': current, 'status': target, 'executable': False}


def list_mcp_tools(db, approved_only=True):
    sql = 'SELECT manifest_digest,name,description,input_schema,status FROM mcp_tools'
    if approved_only:
        sql += " WHERE status='approved'"
    sql += ' ORDER BY manifest_digest,name'
    return [{'id': f"mcp:{r['manifest_digest']}:{r['name']}", 'provider': 'mcp', 'name': r['name'],
             'description': r['description'], 'input_schema': json.loads(r['input_schema']),
             'status': r['status'], 'executable': False} for r in db.execute(sql)]
