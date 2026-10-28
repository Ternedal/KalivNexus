"""Read-only MCP discovery pipeline with injected transport.

The transport must be provided by a trusted caller; this module does not open
network connections, mutate approvals, or execute discovered tools.
"""
from nexus.mcp_client import initialize
from nexus.mcp_discovery import discover_tools
from nexus.mcp_reconcile import reconcile_discovery
from nexus.mcp_sessions import get_session


def inspect_session_tools(db, session_id: str, transport) -> dict:
    """Initialize, discover and reconcile for an existing ready session.

    No approval or execution is granted even if all tool definitions match.
    """
    session = get_session(db, session_id)
    if session['state'] != 'ready':
        raise ValueError('MCP session must be ready')
    connection = db.execute(
        'SELECT manifest_digest, enabled FROM mcp_connections WHERE name=?',
        (session['connection_name'],),
    ).fetchone()
    if connection is None or connection['enabled'] != 0:
        raise ValueError('MCP connection is not eligible for inspection')
    handshake = initialize(transport)
    discovered = discover_tools(transport)
    # Re-check state after external transport interactions (including expiry).
    # Discovery returns normalized metadata; convert it back to the MCP wire
    # shape before reconciliation to avoid losing inputSchema on re-normalization.
    wire_tools = [{'name': t['name'], 'description': t['description'],
                   'inputSchema': t['input_schema']} for t in discovered['tools']]
    reconciliation = reconcile_discovery(db, session_id, {
        'tools': wire_tools, 'count': len(wire_tools),
        'executable': False, 'approved': False,
    })
    return {
        'session_id': session_id,
        'handshake_valid': bool(handshake),
        'discovery_pages': discovered['pages'],
        'discovered_count': discovered['count'],
        'reconciliation': reconciliation,
        'execution_allowed': False,
        'registration_changed': False,
    }


def inspect_registered_connection(db, session_id: str, *, allow_network=False,
                                  transport_factory=None) -> dict:
    """Opt-in inspection using the URL from the registered connection only.

    A caller must supply a trusted, sandboxed transport factory. Never accepts
    a caller-provided URL or enables arbitrary network access by default.
    """
    if not allow_network:
        raise PermissionError('Live MCP inspection is disabled by default')
    if transport_factory is None:
        raise PermissionError('An approved network transport factory is required')
    session = get_session(db, session_id)
    if session['state'] != 'ready':
        raise ValueError('MCP session must be ready')
    connection = db.execute(
        'SELECT url,manifest_digest,enabled FROM mcp_connections WHERE name=?',
        (session['connection_name'],),
    ).fetchone()
    if connection is None or connection['enabled'] != 0:
        raise PermissionError('MCP connection not eligible for inspection')
    from nexus.mcp_connections import validate_profile
    validate_profile(session['connection_name'], connection['url'])
    snapshot = (connection['url'], connection['manifest_digest'])
    transport = transport_factory(connection['url'])
    result = inspect_session_tools(db, session_id, transport)
    latest = db.execute(
        'SELECT url,manifest_digest,enabled FROM mcp_connections WHERE name=?',
        (session['connection_name'],),
    ).fetchone()
    if latest is None or latest['enabled'] != 0 or (latest['url'], latest['manifest_digest']) != snapshot:
        raise PermissionError('MCP connection changed during inspection')
    result['live_transport'] = True
    result['execution_allowed'] = False
    return result


def inspect_via_relay(db, session_id: str, *, relay_host: str, relay_secret: str,
                      relay_port: int = 8787, enabled: bool = False,
                      upstream_url: str | None = None, connection_factory=None) -> dict:
    """Read-only end-to-end inspection through the configured relay.

    The relay's upstream URL must be provisioned separately and bound to the
    registered connection by deployment. This function cannot attest to Docker
    isolation or enable MCP tools/call.
    """
    if not enabled:
        raise PermissionError('Relay inspection disabled by default')
    if not upstream_url:
        raise PermissionError('Explicit relay upstream binding required')
    from nexus.mcp_relay_client import MCPRelayTransport
    kwargs = dict(host=relay_host, port=relay_port, secret=relay_secret, enabled=True)
    if connection_factory is not None:
        kwargs['connection_factory'] = connection_factory

    def factory(registered_url):
        if registered_url != upstream_url:
            raise PermissionError('Relay upstream binding mismatch')
        return MCPRelayTransport(**kwargs)

    result = inspect_registered_connection(
        db, session_id, allow_network=True, transport_factory=factory)
    result['transport'] = 'relay'
    result['isolation_verified'] = False
    return result
