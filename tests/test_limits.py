import pytest
from nexus.limits import ExecutionLimiter


def test_minute_budget_and_recovery():
    now = [0.0]
    limiter = ExecutionLimiter(max_inflight=2, per_minute=2, clock=lambda: now[0])
    for _ in range(2):
        limiter.acquire()
        limiter.release()
    with pytest.raises(PermissionError):
        limiter.acquire()
    now[0] = 60
    limiter.acquire()
    limiter.release()


def test_concurrent_limit_and_release():
    limiter = ExecutionLimiter(max_inflight=1, per_minute=3)
    limiter.acquire()
    with pytest.raises(PermissionError):
        limiter.acquire()
    limiter.release()
    limiter.acquire()
    limiter.release()


def test_bad_limits():
    with pytest.raises(ValueError):
        ExecutionLimiter(max_inflight=0)
    with pytest.raises(ValueError):
        ExecutionLimiter(per_minute=0)
