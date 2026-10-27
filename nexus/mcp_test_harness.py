"""Loopback-only MCP protocol test fixture. Never use for production egress."""
import json
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from nexus.mcp_protocol import PROTOCOL_VERSION

MAX_BYTES = 1024 * 1024

@contextmanager
def local_mcp_server(tools=None):
    """Start an ephemeral loopback HTTP fixture; no tool execution is supported."""
    tools = tools if tools is not None else [{'name': 'echo', 'description': 'Test only', 'inputSchema': {'type': 'object'}}]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_POST(self):
            if self.path != '/mcp':
                self.send_error(404); return
            try:
                length = int(self.headers.get('Content-Length', '-1'))
                if length < 0 or length > MAX_BYTES:
                    self.send_error(413); return
                request = json.loads(self.rfile.read(length))
                method = request.get('method')
                if method == 'initialize':
                    response = {'jsonrpc': '2.0', 'id': request['id'], 'result': {'protocolVersion': PROTOCOL_VERSION, 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'nexus-fixture', 'version': '1.0'}}}
                elif method == 'tools/list':
                    response = {'jsonrpc': '2.0', 'id': request['id'], 'result': {'tools': tools}}
                elif method == 'notifications/initialized':
                    self.send_response(202); self.end_headers(); return
                else:
                    response = {'jsonrpc': '2.0', 'id': request.get('id'), 'error': {'code': -32601, 'message': 'Method not found'}}
                body = json.dumps(response).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers(); self.wfile.write(body)
            except (ValueError, KeyError, TypeError):
                self.send_error(400)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/mcp'
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)

class LoopbackFixtureTransport:
    """Explicitly limited to the ephemeral test server URL."""
    def __init__(self, url):
        from urllib.parse import urlsplit
        parts = urlsplit(url)
        if parts.scheme != 'http' or parts.hostname != '127.0.0.1' or parts.path != '/mcp' or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError('Only the local MCP test fixture is allowed')
        self.url = url
    def _send(self, payload):
        request = Request(self.url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
        with urlopen(request, timeout=3) as response:
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise ValueError('Fixture response too large')
            return response.status, response.headers.get('Content-Type', ''), body
    def exchange(self, payload):
        return self._send(payload)
    def notify(self, payload):
        status, _, _ = self._send(payload)
        if status != 202:
            raise ValueError('Fixture rejected notification')
