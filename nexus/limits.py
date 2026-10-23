"""Process-local execution budgets (not distributed rate limiting)."""
import threading
import time
from collections import deque


class ExecutionLimiter:
    def __init__(self, max_inflight=2, per_minute=20, clock=None):
        if max_inflight < 1 or per_minute < 1:
            raise ValueError('Limits must be positive')
        self.max_inflight = max_inflight
        self.per_minute = per_minute
        self.clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._timestamps = deque()
        self._inflight = 0

    def acquire(self):
        with self._lock:
            now = self.clock()
            while self._timestamps and self._timestamps[0] <= now - 60:
                self._timestamps.popleft()
            if self._inflight >= self.max_inflight or len(self._timestamps) >= self.per_minute:
                raise PermissionError('Execution capacity exceeded')
            self._timestamps.append(now)
            self._inflight += 1

    def release(self):
        with self._lock:
            if self._inflight <= 0:
                raise RuntimeError('Unbalanced release')
            self._inflight -= 1


execution_limiter = ExecutionLimiter()
