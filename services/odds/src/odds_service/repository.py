"""Read side of the fixtures/odds tables (written by app/db.py): matches with nested odds."""

from dataclasses import dataclass
from datetime import date
from itertools import groupby
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row


@dataclass(frozen=True)
class FixtureFilter:
    day: date | None = None
    tz: str = "UTC"  # which calendar day `day` means, e.g. "Africa/Douala"
    tournament_id: int | None = None
    bookmaker: str | None = None  # only fixtures with odds from it, and only its odds
    market_type: str | None = None  # e.g. "1x2", "totals"; only fixtures offering it
    saved_on: date | None = None  # calendar day (in tz) the fixture was last saved

    def where(self) -> tuple[str, list[Any]]:
        clauses, params = [], []
        if self.day is not None:
            clauses.append("(f.start_time AT TIME ZONE %s)::date = %s")
            params += [self.tz, self.day]
        if self.saved_on is not None:
            clauses.append("(f.saved_at AT TIME ZONE %s)::date = %s")
            params += [self.tz, self.saved_on]
        if self.tournament_id is not None:
            clauses.append("f.tournament_id = %s")
            params.append(self.tournament_id)
        if self.bookmaker is not None or self.market_type is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM odds o WHERE o.fixture_id = f.fixture_id"
                " AND (%s::text IS NULL OR o.bookmaker = %s)"
                " AND (%s::text IS NULL OR o.market_type = %s))"
            )
            params += [self.bookmaker, self.bookmaker, self.market_type, self.market_type]
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


_FIXTURE_FIELDS = """
    f.fixture_id, f.sport_id, f.tournament_id, f.tournament_name, f.season_id, f.start_time,
    f.status_id, f.participant1_id, f.participant1_name, f.participant2_id,
    f.participant2_name, f.saved_at
"""

# Grouping order for the nested response: bookmaker -> market -> outcome.
_ODDS_SQL = """
SELECT fixture_id, bookmaker, bookmaker_fixture_id, suspended, market_id, bookmaker_market_id,
       market_name, market_type, period, handicap, market_active, outcome_id, outcome_name,
       player, player_name, price, active, changed_at
FROM odds
WHERE fixture_id = ANY(%s)
  AND (%s::text IS NULL OR bookmaker = %s)
  AND (%s::text IS NULL OR market_type = %s)
ORDER BY fixture_id, bookmaker, market_type, period, handicap, market_id, outcome_id, player
"""


async def list_fixtures(
    conn: AsyncConnection, filters: FixtureFilter, limit: int, offset: int
) -> tuple[int, list[dict[str, Any]]]:
    where, params = filters.where()
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(f"SELECT count(*) AS n FROM fixtures f{where}", params)
        total = (await cur.fetchone())["n"]
        await cur.execute(
            f"SELECT {_FIXTURE_FIELDS} FROM fixtures f{where}"
            " ORDER BY f.start_time, f.fixture_id LIMIT %s OFFSET %s",
            [*params, limit, offset],
        )
        fixtures = await cur.fetchall()
    return total, await _with_odds(conn, fixtures, filters)


async def get_fixture(
    conn: AsyncConnection, fixture_id: str, filters: FixtureFilter
) -> dict[str, Any] | None:
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            f"SELECT {_FIXTURE_FIELDS} FROM fixtures f WHERE f.fixture_id = %s", [fixture_id]
        )
        fixture = await cur.fetchone()
    if fixture is None:
        return None
    return (await _with_odds(conn, [fixture], filters))[0]


async def _with_odds(
    conn: AsyncConnection, fixtures: list[dict[str, Any]], filters: FixtureFilter
) -> list[dict[str, Any]]:
    if not fixtures:
        return []
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            _ODDS_SQL,
            [
                [f["fixture_id"] for f in fixtures],
                filters.bookmaker,
                filters.bookmaker,
                filters.market_type,
                filters.market_type,
            ],
        )
        odds = await cur.fetchall()
    by_fixture = {k: list(rows) for k, rows in groupby(odds, key=lambda r: r["fixture_id"])}
    return [shape_fixture(f, by_fixture.get(f["fixture_id"], [])) for f in fixtures]


def shape_fixture(fixture: dict[str, Any], odds: list[dict[str, Any]]) -> dict[str, Any]:
    """DB rows -> the API shape: match info, then bookmakers -> markets -> outcomes.

    `odds` must be sorted by bookmaker, market, outcome (as _ODDS_SQL returns them).
    """
    bookmakers = []
    for bookmaker, book_rows in groupby(odds, key=lambda r: r["bookmaker"]):
        book_rows = list(book_rows)
        markets = []
        for _, market_rows in groupby(book_rows, key=lambda r: r["market_id"]):
            market_rows = list(market_rows)
            m = market_rows[0]
            markets.append(
                {
                    "marketId": m["market_id"],
                    "bookmakerMarketId": m["bookmaker_market_id"],
                    "name": m["market_name"],
                    "type": m["market_type"],
                    "period": m["period"],
                    "handicap": None if m["handicap"] is None else float(m["handicap"]),
                    "active": m["market_active"],
                    "outcomes": [
                        {
                            "outcomeId": r["outcome_id"],
                            "name": r["outcome_name"],
                            "player": r["player_name"],
                            "price": float(r["price"]),
                            "active": r["active"],
                            "changedAt": r["changed_at"],
                        }
                        for r in market_rows
                    ],
                }
            )
        bookmakers.append(
            {
                "bookmaker": bookmaker,
                "bookmakerFixtureId": book_rows[0]["bookmaker_fixture_id"],
                "suspended": book_rows[0]["suspended"],
                "marketCount": len(markets),
                "markets": markets,
            }
        )
    return {
        "fixtureId": fixture["fixture_id"],
        "startTime": fixture["start_time"],
        "statusId": fixture["status_id"],
        "sportId": fixture["sport_id"],
        "tournament": {"id": fixture["tournament_id"], "name": fixture["tournament_name"]},
        "seasonId": fixture["season_id"],
        "home": {"id": fixture["participant1_id"], "name": fixture["participant1_name"]},
        "away": {"id": fixture["participant2_id"], "name": fixture["participant2_name"]},
        "savedAt": fixture["saved_at"],
        "bookmakers": bookmakers,
    }
