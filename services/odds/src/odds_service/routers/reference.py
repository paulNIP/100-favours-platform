"""Reference data from OddsPapi (sports, bookmakers, tournaments, teams); cached 24h."""

from typing import Any

from fastapi import APIRouter

from ..dependencies import Client, Config, Loader

router = APIRouter(prefix="/v1", tags=["reference"])


@router.get("/sports")
async def sports(client: Client, loader: Loader, cfg: Config) -> Any:
    return await loader.get("sports", cfg.reference_ttl, client.sports)


@router.get("/bookmakers")
async def bookmakers(client: Client, loader: Loader, cfg: Config) -> Any:
    return await loader.get("bookmakers", cfg.reference_ttl, client.bookmakers)


@router.get("/tournaments")
async def tournaments(sport_id: int, client: Client, loader: Loader, cfg: Config) -> Any:
    return await loader.get(
        f"tournaments:{sport_id}", cfg.reference_ttl, lambda: client.tournaments(sport_id)
    )


@router.get("/participants")
async def participants(sport_id: int, client: Client, loader: Loader, cfg: Config) -> Any:
    return await team_names(sport_id, client, loader, cfg)


async def team_names(sport_id: int, client: Client, loader: Loader, cfg: Config) -> dict[str, str]:
    return await loader.get(
        f"participants:{sport_id}", cfg.reference_ttl, lambda: client.participants(sport_id)
    )
