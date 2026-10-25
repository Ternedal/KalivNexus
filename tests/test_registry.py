import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from nexus import db
from nexus.main import app

DOC = {'openapi':'3.0.3','servers':[{'url':'https://example.com'}], 'paths':{'/items':{'get':{'summary':'List items'},'delete':{'summary':'Delete items'}}}}
HEADERS = {'Authorization':'Bearer test-secret'}

def test_registry_is_immutable_and_requires_separate_approval():
    with tempfile.TemporaryDirectory() as tmp:
        db.DB_PATH = Path(tmp) / 'nexus.db'
        with TestClient(app) as client:
            assert client.post('/v1/specs', json={'document':DOC}).status_code == 401
            r = client.post('/v1/specs', json={'document':DOC}, headers=HEADERS)
            assert r.status_code == 200, r.text
            digest = r.json()['digest']
            assert r.json()['created'] is True
            assert client.post('/v1/specs', json={'document':DOC}, headers=HEADERS).json()['created'] is False
            ops = client.get(f'/v1/specs/{digest}/operations',headers=HEADERS).json()
            assert len(ops)==2 and all(op['status']=='discovered' for op in ops)
            op = ops[0]['operation_id']
            path = f'/v1/specs/{digest}/operations/{op}/status'
            assert client.patch(path,json={'status':'approved','reason':'skipping review'},headers=HEADERS).status_code == 409
            assert client.patch(path,json={'status':'reviewed','reason':'manual review'},headers=HEADERS).status_code == 200
            assert client.patch(path,json={'status':'approved','reason':'manual approval'},headers=HEADERS).json()['executable'] is False
            assert len(client.get(f'/v1/specs/{digest}/operations/{op}/reviews',headers=HEADERS).json())==2
            changed = {**DOC, 'info': {'title':'changed'}}
            assert client.post('/v1/specs',json={'document':changed},headers=HEADERS).json()['digest'] != digest
