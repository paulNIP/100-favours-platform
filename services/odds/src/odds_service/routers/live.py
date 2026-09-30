"""Odds fetched from OddsPapi on request (short cache), with team names added."""

from typing import Annotated, Any

from fastapi import APIRouter, Query

from ..dependencies import Client, Config, Loader
from ..oddspapi import OddsPapiError, with_team_names
from .reference import team_names

router = APIRouter(prefix="/v1", tags=["live odds"])


async def name_fixtures(
    fixtures: list[dict[str, Any]], client: Client, loader: Loader, cfg: Config
) -> list[dict[str, Any]]:
    """Add team names to fixtures. Names are a nice-to-have: if the lookup fails
    (e.g. quota), the odds are still returned, with null names."""
    names: dict[str, str] = {}
    for sport_id in {f.get("sportId") for f in fixtures} - {None}:
        try:
            names |= await team_names(sport_id, client, loader, cfg)
        except OddsPapiError:
            pass
    return [with_team_names(f, names) for f in fixtures]


@router.get("/odds/{fixture_id}")
async def odds(fixture_id: str, client: Client, loader: Loader, cfg: Config) -> dict[str, Any]:
    bookmaker_odds = await loader.get(
        f"odds:{fixture_id}", cfg.odds_ttl, lambda: client.odds(fixture_id)
    )
    return {"fixtureId": fixture_id, "bookmakerOdds": bookmaker_odds}


@router.get("/odds")
async def odds_by_tournaments(
    client: Client,
    loader: Loader,
    cfg: Config,
    tournament_ids: Annotated[list[int], Query(min_length=1)],
    bookmaker: str,
) -> Any:
    """Many fixtures in one upstream request, instead of one request per fixture."""
    ids = sorted(set(tournament_ids))
    key = f"odds-by-tournaments:{bookmaker}:{','.join(map(str, ids))}"
    fixtures = await loader.get(
        key, cfg.odds_ttl, lambda: client.odds_by_tournaments(ids, bookmaker)
    )
    return await name_fixtures(fixtures, client, loader, cfg)
