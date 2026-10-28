import tempfile
from pathlib import Path
import pytest
from nexus import db
from nexus.reviews import change_status


def test_review_requires_staged_approval_and_logs():
    with tempfile.TemporaryDirectory() as tmp:
        db.DB_PATH = Path(tmp) / 'test.db'
        with db.connect() as conn:
            conn.execute("INSERT INTO capabilities(id,name,url,category,source) VALUES('x','Example','https://example.org','tools','test')")
            with pytest.raises(ValueError):
                change_status(conn, 'x', 'approved', 'skip review')
            change_status(conn, 'x', 'reviewed', 'Docs and license checked')
            change_status(conn, 'x', 'approved', 'Approved for metadata discovery')
            change_status(conn, 'x', 'disabled', 'Provider unavailable')
            rows = conn.execute('SELECT previous_status,new_status FROM review_events ORDER BY id').fetchall()
            assert [tuple(r) for r in rows] == [('discovered','reviewed'),('reviewed','approved'),('approved','disabled')]


def test_reason_and_missing_capability():
    with tempfile.TemporaryDirectory() as tmp:
        db.DB_PATH = Path(tmp) / 'test.db'
        with db.connect() as conn:
            with pytest.raises(LookupError):
                change_status(conn, 'missing', 'reviewed', 'A real reason')
            conn.execute("INSERT INTO capabilities(id,name,url,category,source) VALUES('y','Y','https://example.org','tools','test')")
            with pytest.raises(ValueError):
                change_status(conn, 'y', 'reviewed', 'no')
