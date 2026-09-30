import httpx
from fastapi.testclient import TestClient
from gateway.config import Settings, get_settings
from gateway.main import app


def client(handler) -> TestClient:
    app.state.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    return TestClient(app)  # no lifespan: keeps the mock transport


def test_routes_to_service_and_strips_prefix(monkeypatch):
    monkeypatch.setattr(
        "gateway.main.get_settings", lambda: Settings(services={"odds": "http://odds:8000"})
    )
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"ok": True}, headers={"x-upstream": "odds"})

    res = client(handler).get("/api/odds/v1/fixtures?limit=1")
    assert res.status_code == 200 and res.json() == {"ok": True}
    assert seen["url"] == "http://odds:8000/v1/fixtures?limit=1"
    assert res.headers["x-upstream"] == "odds"


def test_unknown_service_is_404(monkeypatch):
    monkeypatch.setattr("gateway.main.get_settings", lambda: Settings(services={}))
    assert client(lambda req: httpx.Response(200)).get("/api/nope/x").status_code == 404


def test_unreachable_service_is_503(monkeypatch):
    monkeypatch.setattr(
        "gateway.main.get_settings", lambda: Settings(services={"odds": "http://odds:8000"})
    )

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=req)

    assert client(handler).get("/api/odds/v1/sports").status_code == 503


def test_health():
    assert client(lambda req: httpx.Response(200)).get("/health").json() == {"status": "ok"}
