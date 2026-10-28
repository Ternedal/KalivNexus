"""MCP server connection profiles. No network calls, credentials, or tool execution."""
import ipaddress
import re
from urllib.parse import urlsplit

_NAME = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$')


def validate_profile(name: str, url: str) -> tuple[str, str]:
    if not _NAME.fullmatch(name):
        raise ValueError('Invalid connection name')
    if len(url) > 2048 or any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise ValueError('Invalid URL')
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError('Invalid URL') from exc
    if parsed.scheme != 'https' or not host or parsed.username or parsed.password or parsed.fragment or port not in (None, 443):
        raise ValueError('Only HTTPS port 443 without userinfo or fragments is allowed')
    if host.endswith('.') or host.lower() in ('localhost',) or host.lower().endswith(('.local', '.internal', '.localhost')):
        raise ValueError('Internal host is not allowed')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if '.' not in host or not re.fullmatch(r'[a-zA-Z0-9.-]+', host):
            raise ValueError('Invalid public DNS hostname')
    else:
        raise ValueError('IP literals are not accepted')
    return name, url


def register_connection(db, name: str, url: str, manifest_digest: str) -> dict:
    validate_profile(name, url)
    if not db.execute('SELECT 1 FROM mcp_manifests WHERE digest=?', (manifest_digest,)).fetchone():
        raise LookupError('Manifest not found')
    if db.execute('SELECT 1 FROM mcp_connections WHERE name=?', (name,)).fetchone():
        raise ValueError('Connection name already exists')
    db.execute('INSERT INTO mcp_connections(name,url,manifest_digest,enabled) VALUES(?,?,?,0)', (name,url,manifest_digest))
    return {'name': name, 'url': url, 'manifest_digest': manifest_digest, 'enabled': False, 'connected': False}


def list_connections(db) -> list[dict]:
    return [dict(r) | {'connected': False} for r in db.execute('SELECT name,url,manifest_digest,enabled FROM mcp_connections ORDER BY name')]
