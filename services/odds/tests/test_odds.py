import asyncio

import httpx
import pytest
from odds_service.cache import CachedLoader, MemoryCache
from odds_service.oddspapi import OddsPapiClient, OddsPapiError, with_team_names


def make_client(handler) -> OddsPapiClient:
    http = httpx.AsyncClient(base_url="https://api.test/v4", transport=httpx.MockTransport(handler))
    return OddsPapiClient(http, "secret-key")


async def test_odds_returns_bookmaker_odds():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/v4/odds"
        assert req.url.params["fixtureId"] == "abc"
        assert req.url.params["apiKey"] == "secret-key"
        return httpx.Response(200, json={"bookmakerOdds": {"pinnacle": {"markets": {}}}})

    assert await make_client(handler).odds("abc") == {"pinnacle": {"markets": {}}}


@pytest.mark.parametrize("upstream, expected", [(404, 404), (429, 429), (401, 502), (500, 502)])
async def test_errors_map_status_and_hide_key(upstream, expected):
    client = make_client(lambda req: httpx.Response(upstream))
    with pytest.raises(OddsPapiError) as info:
        await client.odds("abc")
    assert info.value.status_code == expected
    assert "secret-key" not in str(info.value)
    assert info.value.__cause__ is None


async def test_concurrent_requests_share_one_upstream_call():
    calls = 0

    async def load():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return {"ok": True}

    loader = CachedLoader(MemoryCache())
    results = await asyncio.gather(*(loader.get("k", 60, load) for _ in range(20)))
    assert calls == 1
    assert all(r == {"ok": True} for r in results)


async def test_retries_once_on_short_rate_limit():
    responses = [
        httpx.Response(429, json={"error": {"code": "RATE_LIMITED", "retryMs": 5}}),
        httpx.Response(200, json={"bookmakerOdds": {"x": {}}}),
    ]
    client = make_client(lambda req: responses.pop(0))
    assert await client.odds("abc") == {"x": {}}


async def test_not_found_passes_upstream_message():
    body = {"error": {"message": "No fixtures found.", "code": "FIXTURE_NOT_FOUND"}}
    client = make_client(lambda req: httpx.Response(404, json=body))
    with pytest.raises(OddsPapiError) as info:
        await client.odds("abc")
    assert info.value.detail == "No fixtures found."


@pytest.mark.parametrize(
    "raw",
    [
        [
            {"participantId": 6048, "participantName": "Arsenal"},
            {"participantId": 6027, "participantName": "Chelsea"},
        ],
        [{"id": 6048, "name": "Arsenal"}, {"id": 6027, "name": "Chelsea"}],
        {"6048": "Arsenal", "6027": "Chelsea"},
        {"6048": {"participantName": "Arsenal"}, "6027": {"name": "Chelsea"}},
    ],
)
async def test_participants_accepts_known_shapes(raw):
    client = make_client(lambda req: httpx.Response(200, json=raw))
    assert await client.participants(10) == {"6048": "Arsenal", "6027": "Chelsea"}


async def test_unrecognised_participants_shape_is_an_error_not_an_empty_map():
    client = make_client(lambda req: httpx.Response(200, json=[{"foo": 1}]))
    with pytest.raises(OddsPapiError):
        await client.participants(10)


def test_team_names_sit_next_to_ids_and_unknown_ids_are_null():
    fixture = {"fixtureId": "f1", "participant1Id": 6048, "participant2Id": 1, "sportId": 10}
    named = with_team_names(fixture, {"6048": "Arsenal"})
    assert list(named) == [
        "fixtureId",
        "participant1Id",
        "participant1Name",
        "participant2Id",
        "participant2Name",
        "sportId",
    ]
    assert named["participant1Name"] == "Arsenal" and named["participant2Name"] is None
    assert "participant1Name" not in fixture  # the cached original isn't mutated


def test_odds_endpoint_adds_names_and_survives_a_failed_lookup():
    from fastapi.testclient import TestClient
    from odds_service.cache import CachedLoader, MemoryCache
    from odds_service.config import Settings, get_settings
    from odds_service.dependencies import get_client, get_loader
    from odds_service.main import app

    fixtures = [{"fixtureId": "f1", "sportId": 10, "participant1Id": 6048, "participant2Id": 6027}]

    def run(participants_response):
        def handler(req):
            if req.url.path.endswith("/participants"):
                return participants_response
            return httpx.Response(200, json=fixtures)

        loader = CachedLoader(MemoryCache())
        app.dependency_overrides[get_client] = lambda: make_client(handler)
        app.dependency_overrides[get_loader] = lambda: loader
        app.dependency_overrides[get_settings] = lambda: Settings(oddspapi_key="k")
        try:
            return TestClient(app).get("/v1/odds?tournament_ids=1&bookmaker=betpawa.cm")
        finally:
            app.dependency_overrides.clear()

    ok = run(httpx.Response(200, json={"6048": "Arsenal", "6027": "Chelsea"}))
    assert ok.status_code == 200
    assert ok.json()[0]["participant1Name"] == "Arsenal"
    assert ok.json()[0]["participant2Name"] == "Chelsea"

    quota = run(httpx.Response(429, json={"error": {"code": "REQUEST_LIMIT_EXCEEDED"}}))
    assert quota.status_code == 200
    assert quota.json()[0]["participant1Name"] is None
