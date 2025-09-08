import importlib
import io
import os
from fastapi.testclient import TestClient


def _reload_app(monkeypatch, env: dict[str, str]):
    for k, v in env.items():
        if v is None:
            monkeypatch.delenv(k, raising=False)
        else:
            monkeypatch.setenv(k, v)
    import api.main as m
    importlib.reload(m)
    return m, TestClient(m.app)


def test_health_redis_default(monkeypatch):
    m, client = _reload_app(monkeypatch, {
        "KNOT_API_KEY": "secret",
        "REDIS_URL": None,  # ensure not configured
    })
    r = client.get("/health/redis")
    assert r.status_code == 200
    body = r.json()
    assert body.get("configured") is False


def test_ui_served(monkeypatch):
    m, client = _reload_app(monkeypatch, {"KNOT_API_KEY": "secret"})
    r = client.get("/ui")
    # Should serve static HTML UI
    assert r.status_code in (200, 307, 308)


def test_upload_and_preview(monkeypatch):
    # Enable serving uploads
    m, client = _reload_app(monkeypatch, {
        "KNOT_API_KEY": "secret",
        "KNOT_SERVE_UPLOADS": "1",
    })
    data = io.BytesIO(b"hello world")
    files = {"file": ("sample.txt", data, "text/plain")}
    r = client.post("/upload", headers={"x-api-key": "secret"}, files=files)
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("mime") == "text/plain"
    fname = body.get("filename")
    path = body.get("path")
    assert fname and path and os.path.isabs(path)

    # Preview via GET /uploads/{filename}
    r2 = client.get(f"/uploads/{fname}")
    assert r2.status_code == 200
    assert r2.content == b"hello world"


def test_cache_flush_admin(monkeypatch):
    # Seed a cache entry via /search, then flush
    m, client = _reload_app(monkeypatch, {
        "KNOT_API_KEY": "secret",
        "KNOT_CACHE_ENABLED": "1",
    })
    # Seed cache
    client.get("/search", params={"q": "cats", "k": 1})

    # Flush cache (no prefix passed -> default prefix)
    r = client.post("/cache/flush", headers={"x-api-key": "secret"})
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    # memory_cleared >= 0, allow 0 if cache missed
    assert body.get("memory_cleared") is not None
