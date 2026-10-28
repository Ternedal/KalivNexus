"""One-shot execution subprocess with a hard parent-enforced wall-clock budget.

This is process isolation, NOT a network sandbox. Deploy with an egress firewall.
"""
import multiprocessing as mp
import time

from nexus.executor import TOTAL_DEADLINE_SECONDS


def _worker(send, url):
    try:
        from nexus.executor import execute_get
        result = execute_get(url)
        send.send(('ok', result))
    except BaseException as exc:
        # Never leak upstream errors or credentials across the API boundary.
        send.send(('error', type(exc).__name__))
    finally:
        send.close()


def execute_isolated(url: str, *, timeout: float = TOTAL_DEADLINE_SECONDS + 1):
    if not 0 < timeout <= TOTAL_DEADLINE_SECONDS + 2:
        raise ValueError('Invalid supervisor timeout')
    ctx = mp.get_context('spawn')
    receive, send = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_worker, args=(send, url), daemon=True)
    started = time.monotonic()
    try:
        process.start()
        send.close()
        if not receive.poll(max(0, timeout - (time.monotonic() - started))):
            raise TimeoutError('Execution worker exceeded deadline')
        try:
            status, payload = receive.recv()
        except EOFError as exc:
            raise RuntimeError('Execution worker exited unexpectedly') from exc
        if status != 'ok':
            raise RuntimeError('Execution worker failed: ' + str(payload))
        return payload
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
