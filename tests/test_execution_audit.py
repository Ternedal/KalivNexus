from nexus.db import connect
from nexus.execution_audit import record_plan, history


def test_plan_audit_does_not_store_values(tmp_path, monkeypatch):
    import nexus.db as storage
    monkeypatch.setattr(storage, 'DB_PATH', tmp_path / 'nexus.db')
    with connect() as db:
        record_plan(db, 'digest', 'getItem', {'token': 'SUPER_SECRET_VALUE'}, 'denied', 'PermissionError')
        records = history(db, 'digest', 'getItem')
        assert len(records) == 1
        assert records[0]['outcome'] == 'denied'
        assert 'SUPER_SECRET_VALUE' not in str(records)
        assert 'SUPER_SECRET_VALUE' not in db.execute('SELECT * FROM execution_plan_events').fetchone().__str__()


def test_audit_limit_and_order(tmp_path, monkeypatch):
    import nexus.db as storage
    monkeypatch.setattr(storage, 'DB_PATH', tmp_path / 'nexus.db')
    with connect() as db:
        record_plan(db, 'd', 'op', {}, 'denied')
        record_plan(db, 'd', 'op', {}, 'allowed')
        assert [r['outcome'] for r in history(db, 'd', 'op', 1)] == ['allowed']
