import pytest
from nexus.egress import inspect_target


def resolver_for(*ips):
    return lambda *args, **kwargs: [(2, 1, 6, '', (ip, 443)) for ip in ips]


def test_public_dns_requires_pinned_transport():
    result = inspect_target('https://api.example.com/items', resolver_for('8.8.8.8'))
    assert result['safe_to_execute'] is False
    assert result['resolved_addresses'] == ['8.8.8.8']


@pytest.mark.parametrize('ips', [('127.0.0.1',), ('8.8.8.8', '10.0.0.1'), ('169.254.169.254',), ('::1',)])
def test_rejects_private_or_mixed_dns(ips):
    with pytest.raises(PermissionError):
        inspect_target('https://api.example.com/', resolver_for(*ips))


@pytest.mark.parametrize('url', ['http://api.example.com', 'https://localhost', 'https://api.example.com:8443', 'https://127.0.0.1'])
def test_rejects_unsafe_target(url):
    with pytest.raises(PermissionError):
        inspect_target(url, resolver_for('8.8.8.8'))


def test_empty_dns_fails_closed():
    with pytest.raises(PermissionError):
        inspect_target('https://api.example.com', resolver_for())
