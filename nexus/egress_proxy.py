"""Opt-in single-origin MCP egress relay. NOT a substitute for network isolation.

Run as a separate process with an OS-enforced allowlist; bind only to loopback.
"""
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from nexus.egress_proxy_policy import EgressGrant, EgressDenied, authorize_egress
from nexus.relay_attestation import proof
from nexus.mcp_network import MCPNetworkTransport, MAX_BODY, SESSION_RE

SESSION_HEADER = 'Mcp-Session-Id'


class ProxyError(Exception):
    pass


def relay_session(payload: bytes, *, target: str, grant: EgressGrant, session_id: str | None = None,
                  transport_factory=MCPNetworkTransport):
    """Relay one request; carry the upstream MCP session across requests (Codex P2 on #39).

    The relay stays stateless: every request gets a fresh transport, so the
    session travels with the client. The client's Mcp-Session-Id is validated
    and sent upstream, and the session the upstream assigns is returned so the
    handler can forward it. The transport rejects a session the upstream
    changes mid-conversation.
    """
    if session_id is not None and not SESSION_RE.fullmatch(session_id):
        raise ValueError('Invalid MCP session ID')
    authorize_egress(target, 'POST', payload, grant)
    transport = transport_factory(target, enabled=True)
    if session_id is not None:
        transport.session_id = session_id
    status, content_type, response = transport._post(payload)
    if status < 200 or status >= 300:
        raise ProxyError('Upstream MCP request failed')
    if len(response) > MAX_BODY:
        raise ProxyError('Upstream response too large')
    return status, content_type, response, getattr(transport, 'session_id', None)


def relay(payload: bytes, *, target: str, grant: EgressGrant, transport_factory=MCPNetworkTransport):
    status, content_type, response, _ = relay_session(payload, target=target, grant=grant,
                                                      transport_factory=transport_factory)
    return status, content_type, response


def make_handler(*, grant: EgressGrant, secret: str, transport_factory=MCPNetworkTransport):
    if not secret or len(secret) < 32:
        raise ValueError('A strong proxy authentication secret is required')
    if not isinstance(grant, EgressGrant):
        raise ValueError('Explicit egress grant required')

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/attest':
                self.send_error(404)
                return
            auth = self.headers.get('Authorization', '')
            if not hmac.compare_digest(auth, 'Bearer ' + secret):
                self.send_error(403)
                return
            challenge = self.headers.get('X-Nexus-Challenge', '')
            try:
                payload = json.dumps(proof(secret, challenge, grant.origin), separators=(',', ':')).encode('ascii')
            except ValueError:
                self.send_error(400)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            if self.path != '/mcp':
                self.send_error(404)
                return
            auth = self.headers.get('Authorization', '')
            if not hmac.compare_digest(auth, 'Bearer ' + secret):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get('Content-Length', '-1'))
                if length < 0 or length > grant.max_request_bytes:
                    self.send_error(413)
                    return
                body = self.rfile.read(length)
                if len(body) != length:
                    self.send_error(400)
                    return
                session_id = self.headers.get(SESSION_HEADER)
                if session_id is not None and not SESSION_RE.fullmatch(session_id):
                    self.send_error(400)
                    return
                # Destination comes from trusted configuration, never from a client header.
                status, content_type, response, upstream_session = relay_session(
                    body, target=grant.origin, grant=grant, session_id=session_id,
                    transport_factory=transport_factory)
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(response)))
                if upstream_session is not None:
                    self.send_header(SESSION_HEADER, upstream_session)
                self.end_headers()
                self.wfile.write(response)
            except (EgressDenied, PermissionError):
                self.send_error(403)
            except (ValueError, ProxyError, OSError):
                self.send_error(502)

        def log_message(self, format, *args):
            pass  # Never log credentials or request bodies.

    return Handler


def main():
    origin = os.environ['NEXUS_PROXY_ORIGIN']
    secret = os.environ['NEXUS_PROXY_SECRET']
    if urlsplit(origin).query or urlsplit(origin).fragment:
        raise ValueError('Proxy origin must not contain query or fragment')
    grant = EgressGrant(origin=origin)
    authorize_egress(origin, 'POST', b'', grant)
    bind_host = os.environ.get('NEXUS_PROXY_BIND', '127.0.0.1')
    if bind_host not in ('127.0.0.1', '0.0.0.0'):
        raise ValueError('Unsupported proxy bind address')
    if bind_host == '0.0.0.0' and os.environ.get('NEXUS_PROXY_CONTAINER_ISOLATED') != '1':
        raise ValueError('Non-loopback binding requires explicit isolated-container deployment')
    server = ThreadingHTTPServer((bind_host, 8787), make_handler(grant=grant, secret=secret))
    server.serve_forever()


if __name__ == '__main__':
    main()
