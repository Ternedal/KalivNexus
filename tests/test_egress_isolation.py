from pathlib import Path
from unittest.mock import patch
import pytest
from nexus.egress_isolation_probe import probe

ROOT = Path(__file__).resolve().parents[1]


def test_compose_network_is_internal_and_worker_has_no_egress_attachment():
    yaml = (ROOT / 'compose.egress.yaml').read_text()
    assert 'internal: true' in yaml
    worker = yaml.split('  mcp-worker:', 1)[1].split('  mcp-relay:', 1)[0]
    assert 'networks: [worker-internal]' in worker
    assert 'relay-egress' not in worker
    assert 'cap_drop: [ALL]' in worker
    assert 'read_only: true' in worker
    assert 'ports:' not in yaml


def test_probe_fails_closed_when_host_is_unreachable():
    with patch('socket.create_connection', side_effect=OSError('offline')):
        assert probe()['pass'] is False


def test_probe_fails_closed_without_route_information():
    with patch('builtins.open', side_effect=OSError('no proc')):
        assert probe()['pass'] is False


def test_proxy_does_not_bind_publicly_by_default():
    source = (ROOT / 'nexus/egress_proxy.py').read_text()
    assert "os.environ.get('NEXUS_PROXY_BIND', '127.0.0.1')" in source
    assert "NEXUS_PROXY_CONTAINER_ISOLATED" in source
