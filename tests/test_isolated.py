import pytest
from nexus.isolated import execute_isolated


def test_invalid_timeout():
    with pytest.raises(ValueError):
        execute_isolated('https://example.com', timeout=0)


def test_worker_failure_is_bounded():
    with pytest.raises(RuntimeError):
        execute_isolated('https://127.0.0.1', timeout=3)
