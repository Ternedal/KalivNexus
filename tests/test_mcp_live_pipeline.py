import pytest
from nexus.mcp_pipeline import inspect_registered_connection
from test_mcp_reconcile import setup
from test_mcp_pipeline import FakeTransport


def test_live_pipeline_disabled_by_default():
    db, sid, tool, _ = setup()
    with pytest.raises(PermissionError, match='disabled'):
        inspect_registered_connection(db, sid, transport_factory=lambda url: FakeTransport([tool]))


def test_live_pipeline_requires_transport_factory():
    db, sid, _, _ = setup()
    with pytest.raises(PermissionError, match='factory'):
        inspect_registered_connection(db, sid, allow_network=True)


def test_live_pipeline_uses_registered_url_and_never_executes():
    db, sid, tool, _ = setup()
    urls = []
    def factory(url):
        urls.append(url)
        return FakeTransport([tool])
    result = inspect_registered_connection(db, sid, allow_network=True, transport_factory=factory)
    assert urls == ['https://api.example.com/mcp']
    assert result['reconciliation']['manifest_matches']
    assert result['execution_allowed'] is False


def test_live_pipeline_denies_profile_drift():
    db, sid, tool, _ = setup()
    def factory(url):
        db.execute('UPDATE mcp_connections SET url=? WHERE name=?',
                   ('https://changed.example.com/mcp', 'weather'))
        return FakeTransport([tool])
    with pytest.raises(PermissionError, match='changed'):
        inspect_registered_connection(db, sid, allow_network=True, transport_factory=factory)


def test_live_pipeline_denies_closed_session_before_factory():
    from nexus.mcp_sessions import transition_session
    db, sid, tool, _ = setup()
    transition_session(db, sid, 'closed')
    called = []
    with pytest.raises(ValueError, match='ready'):
        inspect_registered_connection(db, sid, allow_network=True,
                                      transport_factory=lambda url: called.append(url))
    assert called == []
