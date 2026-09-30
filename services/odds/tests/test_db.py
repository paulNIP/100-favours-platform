import os
from datetime import UTC, date, datetime

import pytest
from fastapi import HTTPException
from odds_service import db

FIXTURE = {
    "fixtureId": "f1",
    "sportId": 10,
    "tournamentId": 26,
    "startTime": "2026-09-30T16:00:00.000Z",
    "participant1Id": 6048,
    "participant1Name": "Arsenal",
    "participant2Id": 6027,
    "participant2Name": None,
    "bookmakerOdds": {
        "betpawa.cm": {
            "bookmakerFixtureId": "381",
            "suspended": False,
            "markets": {
                "101": {
                    "bookmakerMarketId": "3743",
                    "marketName": "Full Time Result",
                    "marketType": "1x2",
                    "period": "fulltime",
                    "handicap": 0.0,
                    "outcomes": {
                        "101": {
                            "outcomeName": "1",
                            "players": {"0": {"price": 2.1, "active": True}},
                        },
                        "102": {"outcomeName": "X", "players": {"0": {"price": 3.3}}},
                        "103": {"outcomeName": "2", "players": {"0": {"price": None}}},
                    },
                }
            },
        }
    },
}


def test_odds_rows_flatten_and_skip_missing_prices():
    rows = list(db.odds_rows(FIXTURE))
    assert len(rows) == 2
    row = dict(zip(db.ODDS_COLUMNS, rows[0]))
    assert row["market_id"] == 101 and row["outcome_name"] == "1" and row["price"] == 2.1
    assert row["bookmaker_fixture_id"] == "381" and row["player"] == "0"


def test_fixture_row_matches_columns():
    row = dict(zip(db.FIXTURE_COLUMNS, db.fixture_row(FIXTURE, "U21 Euro")))
    assert row["participant1_name"] == "Arsenal" and row["tournament_name"] == "U21 Euro"


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="set TEST_DATABASE_URL to run")
def test_save_is_idempotent_replaces_odds_and_keeps_known_names():
    with db.connect(os.environ["TEST_DATABASE_URL"]) as conn:
        conn.execute("DELETE FROM fixtures WHERE fixture_id = 'f1'")
        assert db.save_fixtures(conn, [FIXTURE], "U21 Euro") == (1, 2)
        assert db.save_fixtures(conn, [FIXTURE], "U21 Euro") == (1, 2)

        # Bookmaker withdraws the draw, and this fetch has no team names.
        changed = {**FIXTURE, "participant1Name": None}
        changed["bookmakerOdds"] = {"betpawa.cm": {**FIXTURE["bookmakerOdds"]["betpawa.cm"]}}
        market = changed["bookmakerOdds"]["betpawa.cm"]["markets"] = {
            "101": {**FIXTURE["bookmakerOdds"]["betpawa.cm"]["markets"]["101"]}
        }
        market["101"]["outcomes"] = {"101": {"outcomeName": "1", "players": {"0": {"price": 2.0}}}}
        db.save_fixtures(conn, [changed])

        odds = conn.execute("SELECT outcome_id, price FROM odds WHERE fixture_id = 'f1'").fetchall()
        name = conn.execute(
            "SELECT participant1_name FROM fixtures WHERE fixture_id = 'f1'"
        ).fetchone()
        conn.execute("DELETE FROM fixtures WHERE fixture_id = 'f1'")
    assert [(o, float(p)) for o, p in odds] == [(101, 2.0)]
    assert name == ("Arsenal",)


def test_shape_fixture_nests_bookmakers_markets_outcomes():
    fixture = dict(zip(db.FIXTURE_COLUMNS, db.fixture_row(FIXTURE, "U21 Euro")))
    fixture |= {"saved_at": None}
    odds = [dict(zip(db.ODDS_COLUMNS, row)) for row in db.odds_rows(FIXTURE)]

    from odds_service.repository import shape_fixture

    shaped = shape_fixture(fixture, odds)
    assert shaped["home"] == {"id": 6048, "name": "Arsenal"}
    assert shaped["tournament"] == {"id": 26, "name": "U21 Euro"}
    [book] = shaped["bookmakers"]
    assert book["bookmaker"] == "betpawa.cm" and book["marketCount"] == 1
    [market] = book["markets"]
    assert market["name"] == "Full Time Result" and market["type"] == "1x2"
    assert [(o["name"], o["price"]) for o in market["outcomes"]] == [("1", 2.1), ("X", 3.3)]


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="set TEST_DATABASE_URL to run")
def test_fixtures_api_lists_and_filters_stored_matches(monkeypatch):
    from fastapi.testclient import TestClient
    from odds_service.config import Settings
    from odds_service.main import app

    url = os.environ["TEST_DATABASE_URL"]
    monkeypatch.setattr(
        "odds_service.main.get_settings", lambda: Settings(oddspapi_key="k", database_url=url)
    )
    with db.connect(url) as conn:
        conn.execute("DELETE FROM fixtures WHERE fixture_id IN ('f1', 'f2')")
        db.save_fixtures(
            conn, [FIXTURE, {**FIXTURE, "fixtureId": "f2", "startTime": "2026-10-01T09:00:00Z"}]
        )

    try:
        with TestClient(app) as http:
            page = http.get("/v1/fixtures", params={"bookmaker": "betpawa.cm"}).json()
            ids = [f["fixtureId"] for f in page["fixtures"] if f["fixtureId"] in ("f1", "f2")]
            assert ids == ["f1", "f2"]  # soonest first
            day = http.get("/v1/fixtures", params={"date": "2026-10-01"}).json()
            assert "f1" not in [f["fixtureId"] for f in day["fixtures"]]
            past = http.get("/v1/fixtures", params={"saved_on": "2000-01-01"}).json()
            assert past["total"] == 0
            one = http.get("/v1/fixtures/f1").json()
            assert one["bookmakers"][0]["markets"][0]["outcomes"][0]["price"] == 2.1
            none = http.get("/v1/fixtures/f1", params={"market_type": "totals"}).json()
            assert none["bookmakers"] == []
            assert http.get("/v1/fixtures/missing").status_code == 404
    finally:
        with db.connect(url) as conn:
            conn.execute("DELETE FROM fixtures WHERE fixture_id IN ('f1', 'f2')")


def test_fixtures_api_without_database_is_503():
    from fastapi.testclient import TestClient
    from odds_service.main import app

    app.state.db = None
    assert TestClient(app).get("/v1/fixtures").status_code == 503


def test_fixture_filter_defaults_to_betpawa_and_all_markets():
    from odds_service.config import Settings
    from odds_service.routers.stored import fixture_filter

    cfg = Settings(oddspapi_key="k")
    default = fixture_filter(cfg=cfg, bookmaker=None, market_type=None, saved_on="today")
    assert default.bookmaker == "betpawa.cm" and default.market_type is None
    assert default.saved_on == datetime.now(UTC).date()
    assert (
        fixture_filter(cfg=cfg, bookmaker="all", market_type=None, saved_on="all").bookmaker is None
    )
    assert (
        fixture_filter(cfg=cfg, bookmaker="all", market_type=None, saved_on="all").saved_on is None
    )
    picked = fixture_filter(cfg=cfg, bookmaker="pinnacle", market_type="1x2", saved_on="2026-09-29")
    assert picked.bookmaker == "pinnacle" and picked.saved_on == date(2026, 9, 29)
    with pytest.raises(HTTPException):
        fixture_filter(cfg=cfg, bookmaker=None, market_type=None, saved_on="yesterday")
