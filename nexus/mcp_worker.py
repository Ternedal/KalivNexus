"""One-shot MCP network worker with parent-enforced timeout.

Process separation is NOT a network sandbox. Only use with OS-level egress rules.
Credentials are intentionally unsupported in this initial worker.
"""
import multiprocessing as mp
import time

from nexus.sandbox import SandboxPolicy, validate_sandbox

MAX_PAYLOAD = 1024 * 1024


def _run(send, url, payload):
    try:
        from nexus.mcp_network import MCPNetworkTransport
        transport = MCPNetworkTransport(url, enabled=True)
        result = transport.exchange(payload)
        send.send(('ok', result))
    except BaseException:
        # Avoid leaking upstream exception strings, URLs or credentials.
        try:
            send.send(('error', None))
        except (BrokenPipeError, OSError):
            pass
    finally:
        send.close()


def exchange_isolated(url: str, payload: bytes, *, enabled=False, timeout=9.0, sandbox_policy: SandboxPolicy | None = None):
    """Execute a single MCP exchange in a child process, opt-in only.

    The caller must enforce network sandboxing and approve the destination.
    No credentials or session state are forwarded to the worker.
    """
    if not enabled:
        raise PermissionError('MCP worker disabled by default')
    if not isinstance(url, str) or not url.startswith('https://'):
        raise ValueError('HTTPS MCP URL required')
    if not isinstance(payload, bytes) or len(payload) > MAX_PAYLOAD:
        raise ValueError('Invalid MCP payload')
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 10:
        raise ValueError('Invalid worker timeout')
    validate_sandbox(url, sandbox_policy)
    ctx = mp.get_context('spawn')
    receive, send = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_run, args=(send, url, payload), daemon=True)
    start = time.monotonic()
    try:
        process.start()
        send.close()
        if not receive.poll(max(0, timeout - (time.monotonic() - start))):
            raise TimeoutError('MCP worker exceeded deadline')
        try:
            status, result = receive.recv()
        except EOFError as exc:
            raise RuntimeError('MCP worker exited without a response') from exc
        if status != 'ok':
            raise RuntimeError('MCP worker failed')
        return result
    finally:
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=0.5)
            if process.is_alive():
                process.kill()
                process.join(timeout=0.5)
        receive.close()
        send.close()
