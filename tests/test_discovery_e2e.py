"""One offline end-to-end discovery smoke through the real HTTP API (ModelRig #2275 item 30).

import -> review -> approve -> discover -> manifest -> audit trail -> OpenAPI spec -> operations,
on the real FastAPI app and SQLite. Only the catalog source is a fixture, and every socket
connect fails the test, so a network call anywhere in the flow is caught.
"""
import socket
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import nexus.main as main
from nexus import db

FIXTURE = """# Weather
- [Open-Meteo](https://api.open-meteo.com/v1/forecast) free weather forecast API
- [Local thing](http://192.168.1.10/api) must be dropped
# Calendar
- [Nager.Date](https://date.nager.at/api/v3) public holidays
"""
TOKEN = "e2e-admin-secret"
ADMIN = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def offline_client(monkeypatch):
    async def fixture_source():
        return FIXTURE, "fixture://api-mega-list"

    def no_network(self, address):
        raise AssertionError(f"network attempted: {address}")

    monkeypatch.setattr(main, "fetch_source", fixture_source)
    monkeypatch.setattr(main, "TOKEN", TOKEN)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(db, "DB_PATH", Path(tmp) / "nexus.db")
        with TestClient(main.app) as client:
            yield client


def test_offline_discovery_flow_end_to_end(offline_client):
    client = offline_client
    imported = client.post("/v1/import", headers=ADMIN)
    assert imported.status_code == 200, imported.text
    assert imported.json() == {"discovered": 2, "inserted": 2, "updated": 0, "source": "fixture://api-mega-list"}

    assert client.get("/v1/discover", params={"q": "weather"}).json()["results"] == [], "unreviewed stays hidden"
    weather = next(c for c in client.get("/v1/capabilities").json() if "open-meteo" in c["url"])
    assert weather["status"] == "discovered"

    for status in ("reviewed", "approved"):
        changed = client.patch(f"/v1/capabilities/{weather['id']}/status", headers=ADMIN,
                               json={"status": status, "reason": "offline e2e review"})
        assert changed.status_code == 200, changed.text
        assert changed.json()["status"] == status

    found = client.get("/v1/discover", params={"q": "weather forecast"}).json()
    assert [r["id"] for r in found["results"]] == [weather["id"]]
    assert found["execution_enabled"] is False

    assert client.get("/v1/manifest").status_code == 401
    manifest = client.get("/v1/manifest", headers=ADMIN).json()
    assert [c["id"] for c in manifest["capabilities"]] == [weather["id"]], "only approved entries are exported"
    assert manifest["executable"] is False

    trail = client.get(f"/v1/capabilities/{weather['id']}/reviews", headers=ADMIN).json()
    assert [e["new_status"] for e in trail] == ["reviewed", "approved"]
    assert [e["previous_status"] for e in trail] == ["discovered", "reviewed"]

    document = {"openapi": "3.0.3", "info": {"title": "Open-Meteo", "version": "1"},
                "servers": [{"url": "https://api.open-meteo.com"}],
                "paths": {"/v1/forecast": {"get": {"operationId": "forecast",
                                                   "responses": {"200": {"description": "ok"}}}}}}
    registered = client.post("/v1/specs", headers=ADMIN, json={"document": document})
    assert registered.status_code == 200, registered.text
    digest = registered.json()["digest"]
    again = client.post("/v1/specs", headers=ADMIN, json={"document": document})
    assert again.json()["digest"] == digest, "content-addressed: the same document gives the same digest"

    operations = client.get(f"/v1/specs/{digest}/operations", headers=ADMIN).json()
    assert [(o["method"], o["path"], o["name"], o["status"]) for o in operations] == [
        ("GET", "/v1/forecast", "forecast", "discovered")]
