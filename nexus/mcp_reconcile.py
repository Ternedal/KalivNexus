"""Fail-closed reconciliation of discovered MCP tools with an approved manifest.

No network calls, database mutations or execution are performed here.
"""
import hashlib
import json
from nexus.tools import normalize_mcp_manifest
from nexus.mcp_sessions import get_session


def reconcile_discovery(db, session_id: str, discovery: dict) -> dict:
    session = get_session(db, session_id)
    if session['state'] != 'ready':
        raise ValueError('MCP session must be ready')
    connection = db.execute(
        'SELECT manifest_digest, enabled FROM mcp_connections WHERE name=?',
        (session['connection_name'],)).fetchone()
    if connection is None:
        raise ValueError('MCP connection no longer exists')
    # Connection profiles are intentionally disabled in the current schema.
    if connection['enabled'] != 0:
        raise ValueError('Unexpected connection configuration')
    if not isinstance(discovery, dict) or discovery.get('executable') is not False or discovery.get('approved') is not False:
        raise ValueError('Expected non-executable discovery result')
    tools = normalize_mcp_manifest({'tools': discovery.get('tools')})
    if discovery.get('count') != len(tools):
        raise ValueError('Discovery count mismatch')
    digest = connection['manifest_digest']
    rows = db.execute(
        'SELECT name,description,input_schema,status FROM mcp_tools WHERE manifest_digest=?',
        (digest,)).fetchall()
    registered = {r['name']: r for r in rows}
    found = {t['name']: t for t in tools}
    unchanged, changed, added, removed = [], [], [], []
    for name in sorted(set(found) | set(registered)):
        if name not in registered:
            added.append(name)
        elif name not in found:
            removed.append(name)
        else:
            row = registered[name]
            t = found[name]
            schema = json.loads(row['input_schema'])
            if row['description'] == t['description'] and schema == t['input_schema']:
                unchanged.append(name)
            else:
                changed.append(name)
    approved = sorted(name for name in unchanged if registered[name]['status'] == 'approved')
    canonical = json.dumps(tools, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    observed_digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    # The entire manifest must match, not merely individual approved tool names.
    manifest_matches = observed_digest == digest and not (changed or added or removed)
    return {
        'session_id': session_id, 'manifest_digest': digest,
        'observed_digest': observed_digest, 'manifest_matches': manifest_matches,
        'unchanged': unchanged, 'changed': changed, 'added': added, 'removed': removed,
        'approved_matching_tools': approved if manifest_matches else [],
        'execution_allowed': False, 'registration_changed': False,
    }
