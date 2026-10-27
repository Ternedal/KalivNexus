from pathlib import Path
from nexus.sandbox_probe import probe


def test_probe_returns_expected_fields():
    result = probe()
    assert set(result) == {'external_ipv4', 'loopback_ipv4', 'no_ipv4_routes', 'pass'}
    assert isinstance(result['pass'], bool)


def test_sandbox_compose_denies_network_and_privileges():
    content = (Path(__file__).resolve().parents[1] / 'compose.sandbox.yaml').read_text()
    for required in ('network_mode: none', 'read_only: true', 'cap_drop: [ALL]',
                     'no-new-privileges:true', 'pids_limit:', 'mem_limit:',
                     'nexus.sandbox_probe', 'profiles: [sandbox-test]'):
        assert required in content
