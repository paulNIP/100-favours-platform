"""Fixtures and odds saved in Postgres by scripts.export_odds / import_json."""

from datetime import date, datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import repository
from ..dependencies import Config, Db

router = APIRouter(prefix="/v1", tags=["stored fixtures"])


def fixture_filter(
    cfg: Config,
    day: Annotated[date | None, Query(alias="date", description="yyyy-mm-dd kick-off day")] = None,
    tz: Annotated[str, Query(description="time zone for `date`, e.g. Africa/Douala")] = "UTC",
    tournament_id: int | None = None,
    bookmaker: Annotated[
        str | None, Query(description="default: betpawa.cm; 'all' for every bookmaker")
    ] = None,
    market_type: Annotated[
        str | None, Query(description="default: all; or one type, e.g. 1x2, totals, spreads")
    ] = None,
    saved_on: Annotated[
        str,
        Query(description="day saved_at falls on (in tz): 'today' (default), yyyy-mm-dd or 'all'"),
    ] = "today",
) -> repository.FixtureFilter:
    bookmaker = bookmaker or cfg.default_bookmaker
    if bookmaker == "all":
        bookmaker = None
    try:
        zone = ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, f"Unknown time zone '{tz}'") from None
    return repository.FixtureFilter(
        day, tz, tournament_id, bookmaker, market_type, parse_saved_on(saved_on, zone)
    )


def parse_saved_on(value: str, zone: ZoneInfo) -> date | None:
    if value == "all":
        return None
    if value == "today":
        return datetime.now(zone).date()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, "saved_on must be 'today', 'all' or yyyy-mm-dd") from None


Filters = Annotated[repository.FixtureFilter, Depends(fixture_filter)]


@router.get("/fixtures")
async def stored_fixtures(
    conn: Db,
    filters: Filters,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    """Saved matches, soonest first, with all their markets and odds (betpawa.cm by default)."""
    total, fixtures = await repository.list_fixtures(conn, filters, limit, offset)
    return {"total": total, "limit": limit, "offset": offset, "fixtures": fixtures}


@router.get("/fixtures/{fixture_id}")
async def stored_fixture(fixture_id: str, conn: Db, filters: Filters) -> dict[str, Any]:
    fixture = await repository.get_fixture(conn, fixture_id, filters)
    if fixture is None:
        raise HTTPException(404, f"Fixture '{fixture_id}' not found")
    return fixture
