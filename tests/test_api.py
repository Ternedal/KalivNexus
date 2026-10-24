import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["NEXUS_ADMIN_TOKEN"] = "test-secret"
from nexus import db
from nexus.main import app

def test_health_and_auth():
    with tempfile.TemporaryDirectory() as tmp:
        db.DB_PATH = Path(tmp) / "nexus.db"
        with TestClient(app) as client:
            assert client.get("/healthz").status_code == 200
            assert client.get("/v1/capabilities").json() == []
            assert client.post("/v1/import").status_code == 401
            assert client.get("/v1/categories").status_code == 200

