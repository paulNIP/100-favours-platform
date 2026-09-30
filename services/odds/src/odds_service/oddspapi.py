import asyncio
from typing import Any

import httpx
from platform_common import UpstreamError


class OddsPapiError(UpstreamError):
    pass


# OddsPapi enforces a short per-endpoint burst limit and says how long to wait.
MAX_RETRY_WAIT_MS = 1000


class OddsPapiClient:
    """Thin async wrapper around the OddsPapi v4 REST API.

    The API key travels as a query param, so errors are re-raised without the
    original exception chain to keep the full URL out of logs and tracebacks.
    """

    def __init__(self, http: httpx.AsyncClient, api_key: str):
        self._http = http
        self._key = api_key

    async def _get(self, path: str, **params: Any) -> Any:
        query = {k: v for k, v in params.items() if v is not None}
        query["apiKey"] = self._key
        res = await self._send(path, query)
        if res.status_code == 429 and (wait := _retry_ms(res)) is not None:
            await asyncio.sleep(wait / 1000)
            res = await self._send(path, query)

        if res.is_success:
            return res.json()
        if res.status_code == 404:
            raise OddsPapiError(404, _error_message(res) or "Not found at OddsPapi")
        if res.status_code == 429:
            raise OddsPapiError(429, "OddsPapi quota exceeded")
        # 401/403 mean our key is bad: that's our failure, not the caller's.
        raise OddsPapiError(502, f"OddsPapi {res.status_code}")

    async def _send(self, path: str, query: dict[str, Any]) -> httpx.Response:
        try:
            return await self._http.get(path, params=query)
        except httpx.HTTPError as exc:
            raise OddsPapiError(502, f"OddsPapi unreachable ({type(exc).__name__})") from None

    async def sports(self) -> Any:
        return await self._get("/sports")

    async def tournaments(self, sport_id: int) -> Any:
        return await self._get("/tournaments", sportId=sport_id)

    async def participants(self, sport_id: int) -> dict[str, str]:
        """participantId -> team name. Keys are strings so the map survives the JSON cache."""
        raw = await self._get("/participants", sportId=sport_id)
        names = participant_names(raw)
        if raw and not names:
            # Don't let an unrecognised shape be cached as "no names" for a day.
            raise OddsPapiError(502, "Unrecognised OddsPapi participants response")
        return names

    async def bookmakers(self) -> Any:
        return await self._get("/bookmakers")

    async def markets(self, sport_id: int) -> Any:
        return await self._get("/markets", sportId=sport_id)

    async def odds(self, fixture_id: str) -> dict[str, Any]:
        # data.bookmakerOdds[bookmaker].markets[marketId].outcomes[outcomeId].players[0].price
        data = await self._get("/odds", fixtureId=fixture_id)
        return data.get("bookmakerOdds", {})

    async def odds_by_tournaments(self, tournament_ids: list[int], bookmaker: str) -> Any:
        return await self._get(
            "/odds-by-tournaments",
            tournamentIds=",".join(map(str, tournament_ids)),
            bookmaker=bookmaker,
        )


def participant_names(raw: Any) -> dict[str, str]:
    # The response shape isn't documented: accept an id -> name map or a list of objects.
    if isinstance(raw, dict):
        items = raw.items()
    elif isinstance(raw, list):
        items = ((p.get("participantId", p.get("id")), p) for p in raw if isinstance(p, dict))
    else:
        return {}
    names = {}
    for pid, value in items:
        name = value if isinstance(value, str) else _name(value)
        if pid is not None and name:
            names[str(pid)] = name
    return names


def _name(participant: Any) -> str | None:
    if not isinstance(participant, dict):
        return None
    for key in ("participantName", "name", "shortName"):
        if participant.get(key):
            return participant[key]
    return None


def with_team_names(fixture: dict[str, Any], names: dict[str, str]) -> dict[str, Any]:
    """Copy of the fixture with participant1Name/participant2Name next to their ids."""
    out: dict[str, Any] = {}
    for key, value in fixture.items():
        out[key] = value
        if key in ("participant1Id", "participant2Id"):
            out[key.replace("Id", "Name")] = names.get(str(value))
    return out


def _error_body(res: httpx.Response) -> dict[str, Any]:
    try:
        return res.json().get("error") or {}
    except (ValueError, AttributeError):
        return {}


def _error_message(res: httpx.Response) -> str | None:
    return _error_body(res).get("message")


def _retry_ms(res: httpx.Response) -> int | None:
    ms = _error_body(res).get("retryMs")
    return ms if isinstance(ms, int) and 0 <= ms <= MAX_RETRY_WAIT_MS else None
