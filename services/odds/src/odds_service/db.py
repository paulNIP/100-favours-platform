"""Postgres persistence for fixtures and their odds.

fixtures  one row per fixture (teams, tournament, kick-off), upserted
odds      one row per fixture / bookmaker / market / outcome / player: the latest
          snapshot. Each save replaces that fixture+bookmaker's rows, so outcomes
          the bookmaker has withdrawn don't linger with stale prices.
"""

from collections.abc import Iterable, Iterator
from typing import Any

import psycopg

SCHEMA = """
CREATE TABLE IF NOT EXISTS fixtures (
    fixture_id        text PRIMARY KEY,
    sport_id          integer,
    tournament_id     integer,
    tournament_name   text,
    season_id         integer,
    start_time        timestamptz,
    status_id         integer,
    participant1_id   integer,
    participant1_name text,
    participant2_id   integer,
    participant2_name text,
    has_odds          boolean,
    upstream_updated_at timestamptz,
    saved_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fixtures_start_time_idx ON fixtures (start_time);
CREATE INDEX IF NOT EXISTS fixtures_tournament_idx ON fixtures (tournament_id);

CREATE TABLE IF NOT EXISTS odds (
    fixture_id          text NOT NULL REFERENCES fixtures ON DELETE CASCADE,
    bookmaker           text NOT NULL,
    market_id           integer NOT NULL,
    outcome_id          integer NOT NULL,
    player              text NOT NULL,
    bookmaker_fixture_id text,
    bookmaker_market_id text,
    market_name         text,
    market_type         text,
    period              text,
    handicap            numeric,
    outcome_name        text,
    player_name         text,
    price               numeric NOT NULL,
    active              boolean,
    market_active       boolean,
    suspended           boolean,
    changed_at          timestamptz,
    saved_at            timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (fixture_id, bookmaker, market_id, outcome_id, player)
);
CREATE INDEX IF NOT EXISTS odds_market_idx ON odds (market_type, period, handicap);
"""

FIXTURE_COLUMNS = (
    "fixture_id",
    "sport_id",
    "tournament_id",
    "tournament_name",
    "season_id",
    "start_time",
    "status_id",
    "participant1_id",
    "participant1_name",
    "participant2_id",
    "participant2_name",
    "has_odds",
    "upstream_updated_at",
)
ODDS_COLUMNS = (
    "fixture_id",
    "bookmaker",
    "market_id",
    "outcome_id",
    "player",
    "bookmaker_fixture_id",
    "bookmaker_market_id",
    "market_name",
    "market_type",
    "period",
    "handicap",
    "outcome_name",
    "player_name",
    "price",
    "active",
    "market_active",
    "suspended",
    "changed_at",
)

_UPSERT_FIXTURE = f"""
INSERT INTO fixtures ({", ".join(FIXTURE_COLUMNS)})
VALUES ({", ".join(["%s"] * len(FIXTURE_COLUMNS))})
ON CONFLICT (fixture_id) DO UPDATE SET
    {", ".join(f"{c} = COALESCE(EXCLUDED.{c}, fixtures.{c})" for c in FIXTURE_COLUMNS[1:])},
    saved_at = now()
"""
_INSERT_ODDS = f"""
INSERT INTO odds ({", ".join(ODDS_COLUMNS)})
VALUES ({", ".join(["%s"] * len(ODDS_COLUMNS))})
"""


def connect(url: str) -> psycopg.Connection:
    conn = psycopg.connect(url)
    with conn.transaction():
        conn.execute(SCHEMA)
    return conn


def fixture_row(fixture: dict[str, Any], tournament_name: str | None = None) -> tuple:
    return (
        fixture["fixtureId"],
        fixture.get("sportId"),
        fixture.get("tournamentId"),
        tournament_name,
        fixture.get("seasonId"),
        fixture.get("startTime"),
        fixture.get("statusId"),
        fixture.get("participant1Id"),
        fixture.get("participant1Name"),  # COALESCE keeps a name saved earlier if now missing
        fixture.get("participant2Id"),
        fixture.get("participant2Name"),
        fixture.get("hasOdds"),
        fixture.get("updatedAt"),
    )


def odds_rows(fixture: dict[str, Any]) -> Iterator[tuple]:
    for bookmaker, book in (fixture.get("bookmakerOdds") or {}).items():
        for market_id, market in (book.get("markets") or {}).items():
            for outcome_id, outcome in (market.get("outcomes") or {}).items():
                for player, quote in (outcome.get("players") or {}).items():
                    if quote.get("price") is None:
                        continue
                    yield (
                        fixture["fixtureId"],
                        bookmaker,
                        int(market_id),
                        int(outcome_id),
                        str(player),
                        book.get("bookmakerFixtureId"),
                        market.get("bookmakerMarketId"),
                        market.get("marketName"),
                        market.get("marketType"),
                        market.get("period"),
                        market.get("handicap"),
                        outcome.get("outcomeName"),
                        quote.get("playerName"),
                        quote["price"],
                        quote.get("active"),
                        market.get("marketActive"),
                        book.get("suspended"),
                        quote.get("changedAt"),
                    )


def save_fixtures(
    conn: psycopg.Connection,
    fixtures: Iterable[dict[str, Any]],
    tournament_name: str | None = None,
) -> tuple[int, int]:
    """Upsert fixtures and replace their odds, all in one transaction. -> (fixtures, odds)."""
    fixtures = list(fixtures)
    rows = [row for f in fixtures for row in odds_rows(f)]
    books = {(f["fixtureId"], b) for f in fixtures for b in (f.get("bookmakerOdds") or {})}
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(_UPSERT_FIXTURE, [fixture_row(f, tournament_name) for f in fixtures])
        cur.executemany("DELETE FROM odds WHERE fixture_id = %s AND bookmaker = %s", list(books))
        cur.executemany(_INSERT_ODDS, rows)
    return len(fixtures), len(rows)
