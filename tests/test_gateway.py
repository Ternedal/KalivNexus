import pytest
from nexus.db import connect
from nexus.registry import register, transition
from nexus.gateway import plan


def test_approval_gated_inert_plan(tmp_path, monkeypatch):
    import nexus.db as storage
    monkeypatch.setattr(storage, 'DB_PATH', tmp_path / 'nexus.db')
    document = {'openapi': '3.0.3', 'servers': [{'url': 'https://example.com'}],
                'paths': {'/items/{item}': {'get': {'summary': 'Read item', 'security': [{'apiKey': []}]}}}}
    with connect() as db:
        spec = register(db, document)
        digest = spec['digest']
        op = db.execute('SELECT operation_id FROM api_operations').fetchone()[0]
        with pytest.raises(PermissionError):
            plan(db, digest, op, {'item': 'hello'})
        transition(db, digest, op, 'reviewed', 'Reviewed manually')
        transition(db, digest, op, 'approved', 'Approved manually')
        result = plan(db, digest, op, {'item': 'hello/world'})
        assert result['target_url'] == 'https://example.com/items/hello%2Fworld'
        assert result['execution_enabled'] is False
        with pytest.raises(ValueError):
            plan(db, digest, op, {'other': 'x'})


def test_reject_private_host(tmp_path, monkeypatch):
    import nexus.db as storage
    monkeypatch.setattr(storage, 'DB_PATH', tmp_path / 'nexus.db')
    doc = {'openapi': '3.0.3', 'servers': [{'url': 'https://127.0.0.1'}],
           'paths': {'/ping': {'get': {'summary': 'Ping'}}}}
    with connect() as db:
        digest = register(db, doc)['digest']
        op = db.execute('SELECT operation_id FROM api_operations').fetchone()[0]
        transition(db, digest, op, 'reviewed', 'Reviewed manually')
        transition(db, digest, op, 'approved', 'Approved manually')
        with pytest.raises(PermissionError):
            plan(db, digest, op, {})
