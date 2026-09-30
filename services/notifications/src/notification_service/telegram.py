import asyncio
from typing import Any

import httpx
from platform_common import UpstreamError


class TelegramError(UpstreamError):
    pass


# Telegram's flood control says how long to wait; only wait if it's short.
MAX_RETRY_AFTER_S = 3


class TelegramClient:
    """Thin async wrapper around the Telegram Bot API.

    The bot token is part of the URL path, so errors are re-raised without the
    original exception chain to keep it out of logs and tracebacks.
    """

    def __init__(self, http: httpx.AsyncClient, bot_token: str):
        self._http = http
        self._token = bot_token

    async def _call(self, method: str, payload: dict[str, Any]) -> Any:
        body = {k: v for k, v in payload.items() if v is not None}
        res = await self._send(method, body)
        if res.status_code == 429 and (wait := _retry_after(res)) is not None:
            await asyncio.sleep(wait)
            res = await self._send(method, body)

        data = _json(res)
        if res.is_success and data.get("ok"):
            return data["result"]
        description = data.get("description") or f"Telegram {res.status_code}"
        # 400 (bad chat id / markup) and 403 (bot blocked or not in chat) are the caller's to fix.
        if res.status_code in (400, 403):
            raise TelegramError(res.status_code, description)
        if res.status_code == 429:
            raise TelegramError(429, "Telegram rate limit exceeded")
        # 401/404 mean our token is bad: that's our failure, not the caller's.
        raise TelegramError(502, f"Telegram {res.status_code}")

    async def _send(self, method: str, body: dict[str, Any]) -> httpx.Response:
        try:
            return await self._http.post(f"/bot{self._token}/{method}", json=body)
        except httpx.HTTPError as exc:
            raise TelegramError(502, f"Telegram unreachable ({type(exc).__name__})") from None

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
        disable_notification: bool | None = None,
    ) -> dict[str, Any]:
        return await self._call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_notification": disable_notification,
            },
        )


def _json(res: httpx.Response) -> dict[str, Any]:
    try:
        data = res.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _retry_after(res: httpx.Response) -> int | None:
    s = (_json(res).get("parameters") or {}).get("retry_after")
    return s if isinstance(s, int) and 0 <= s <= MAX_RETRY_AFTER_S else None
