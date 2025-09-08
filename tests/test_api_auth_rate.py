import importlib
import os
from fastapi.testclient import TestClient


def test_api_auth_and_rate_limit(monkeypatch):
    # Enable API key auth
    monkeypatch.setenv("KNOT_API_KEY", "secret")
    import api.main as m
    importlib.reload(m)

    client = TestClient(m.app)

    # Unauthorized request should fail
    r = client.post("/users", json={})
    assert r.status_code == 401

    # Authorized should pass
    r = client.post("/users", headers={"x-api-key": "secret"}, json={"username": "t1"})
    assert r.status_code == 200
    u = r.json()
    assert u.get("userID")

    # Rate-limit smoke (search is public; default 60/min). Do small loop to keep test fast.
    # We won't actually trip the limit here to avoid flakiness; just ensure 200s.
    for _ in range(5):
        r = client.get("/search", params={"q": "cats", "k": 1})
        assert r.status_code == 200

    # Now simulate hitting the limit by resetting store and calling many times.
    m._rate_store.clear()
    # Perform 65 requests to exceed default of 60
    status_codes = []
    for _ in range(65):
        resp = client.get("/search", params={"q": "cats", "k": 1})
        status_codes.append(resp.status_code)
    assert 429 in status_codes
