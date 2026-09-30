import json

import httpx
import pytest
from fastapi.testclient import TestClient
from notification_service.config import Settings, get_settings
from notification_service.main import app
from notification_service.routes import get_client
from notification_service.telegram import TelegramClient, TelegramError

TOKEN = "123:secret-token"


def make_client(handler) -> TelegramClient:
    http = httpx.AsyncClient(base_url="https://tg.test", transport=httpx.MockTransport(handler))
    return TelegramClient(http, TOKEN)


def ok(chat_id: int = 42, message_id: int = 7) -> httpx.Response:
    return httpx.Response(
        200, json={"ok": True, "result": {"message_id": message_id, "chat": {"id": chat_id}}}
    )


async def test_send_message_posts_to_bot_method():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == f"/bot{TOKEN}/sendMessage"
        assert json.loads(req.content) == {"chat_id": "42", "text": "hi", "parse_mode": "HTML"}
        return ok()

    result = await make_client(handler).send_message("42", "hi", parse_mode="HTML")
    assert result["message_id"] == 7


@pytest.mark.parametrize(
    "upstream, expected", [(400, 400), (403, 403), (429, 429), (401, 502), (500, 502)]
)
async def test_errors_map_status_and_hide_token(upstream, expected):
    client = make_client(lambda req: httpx.Response(upstream, json={"ok": False}))
    with pytest.raises(TelegramError) as info:
        await client.send_message("42", "hi")
    assert info.value.status_code == expected
    assert TOKEN not in str(info.value)
    assert info.value.__cause__ is None


async def test_bad_request_passes_telegram_description():
    body = {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}
    client = make_client(lambda req: httpx.Response(400, json=body))
    with pytest.raises(TelegramError) as info:
        await client.send_message("42", "hi")
    assert info.value.detail == "Bad Request: chat not found"


async def test_retries_once_on_short_flood_wait():
    responses = [
        httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 0}}),
        ok(),
    ]
    client = make_client(lambda req: responses.pop(0))
    assert (await client.send_message("42", "hi"))["message_id"] == 7


def make_app(handler, default_chat_id: str | None = None) -> TestClient:
    app.dependency_overrides[get_client] = lambda: make_client(handler)
    app.dependency_overrides[get_settings] = lambda: Settings(
        telegram_bot_token=TOKEN, telegram_default_chat_id=default_chat_id
    )
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


def test_endpoint_uses_default_chat_id():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(json.loads(req.content))
        return ok(chat_id=-100)

    res = make_app(handler, default_chat_id="-100").post(
        "/v1/telegram/messages", json={"text": "Odds updated"}
    )
    assert res.status_code == 201
    assert res.json() == {"chat_id": "-100", "message_id": 7}
    assert seen == {"chat_id": "-100", "text": "Odds updated"}


def test_endpoint_requires_a_chat_id():
    res = make_app(lambda req: ok()).post("/v1/telegram/messages", json={"text": "hi"})
    assert res.status_code == 422


def test_endpoint_rejects_text_over_telegram_limit():
    res = make_app(lambda req: ok()).post(
        "/v1/telegram/messages", json={"chat_id": "42", "text": "x" * 4097}
    )
    assert res.status_code == 422


def test_templates_endpoint_lists_variables():
    res = make_app(lambda req: ok()).get("/v1/telegram/templates")
    assert res.status_code == 200
    assert len(res.json()) == 10
    assert res.json()["quiz"] == ["question", "answer"]
    assert res.json()["help"] == []


def test_template_is_rendered_escaped_and_sent_as_html():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(json.loads(req.content))
        return ok()

    res = make_app(handler, default_chat_id="42").post(
        "/v1/telegram/templates/service_down",
        json={
            "variables": {
                "service_name": "odds-service",
                "status_code": 502,
                "timestamp": "2026-09-30 16:00",
                "error_message": "<html> & friends",
            }
        },
    )
    assert res.status_code == 201
    assert seen["parse_mode"] == "HTML"
    assert "<b>Service:</b> odds-service" in seen["text"]
    assert "<b>Status:</b> 502" in seen["text"]
    assert "<pre>&lt;html&gt; &amp; friends</pre>" in seen["text"]


def test_every_template_renders():
    from notification_service import templates

    for name in templates.TEMPLATES:
        text = templates.render(name, {f: "x" for f in templates.fields(name)})
        assert "{" not in text and "}" not in text


@pytest.mark.parametrize(
    "variables, message",
    [
        ({"question": "Q?"}, "missing variables: answer"),
        ({"question": "Q?", "answer": "A", "anwser": "A"}, "unknown variables: anwser"),
    ],
)
def test_template_rejects_missing_and_unknown_variables(variables, message):
    res = make_app(lambda req: ok()).post(
        "/v1/telegram/templates/quiz", json={"chat_id": "42", "variables": variables}
    )
    assert res.status_code == 422
    assert res.json()["detail"] == message


def test_unknown_template_is_404():
    res = make_app(lambda req: ok()).post("/v1/telegram/templates/nope", json={"chat_id": "42"})
    assert res.status_code == 404
