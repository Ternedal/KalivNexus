import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from nexus import db
from nexus.discovery import rank
from nexus.main import app

def test_ranking():
    rows = [dict(id='a',name='Weather forecast',category='Weather',description='temperature and rain'),
            dict(id='b',name='Jobs',category='Careers',description='employment')]
    assert rank('weather temperature', rows)[0]['id'] == 'a'
    assert rank('zzzzzz', rows) == []

def test_discovery_approval_gate():
    with tempfile.TemporaryDirectory() as tmp:
        db.DB_PATH = Path(tmp) / 'nexus.db'
        with TestClient(app) as client:
            with db.connect() as conn:
                conn.execute("INSERT INTO capabilities (id,name,url,category,description,source,status) VALUES (?,?,?,?,?,?,?)",
                             ('w','Weather API','https://example.org','Weather','forecast','test','discovered'))
            assert client.get('/v1/discover',params={'q':'weather'}).json()['results'] == []
            assert len(client.get('/v1/discover',params={'q':'weather','approved_only':'false'}).json()['results']) == 1
            assert client.get('/v1/manifest').status_code == 401
            with db.connect() as conn:
                conn.execute("UPDATE capabilities SET status='approved' WHERE id='w'")
            assert len(client.get('/v1/discover',params={'q':'weather'}).json()['results']) == 1
