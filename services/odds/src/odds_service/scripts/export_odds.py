"""Export odds for every active tournament of a sport, one upstream call per tournament.

    uv run odds-export --sport-id 10 --bookmaker betpawa.cm        # from the repo root

Writes <ODDS_DATA_DIR>/<bookmaker>/<sport-slug>/<yyyy-mm-dd>-<tournamentId>-<tournamentSlug>.json,
keeping only fixtures that start on that date (local time; --date to override).
Tournaments already saved for the date are skipped without an upstream call.
Only tournaments with upcoming or live fixtures are fetched, to save quota.
Each market gets its name/type/period/handicap and each outcome its name, and each
fixture its team names (participant1Name / participant2Name). Already-saved files
that lack team names get them added, without re-fetching the odds.
With DATABASE_URL set, fixtures and odds are also saved to Postgres (see app/db.py).
"""

import argparse
import asyncio
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx

from odds_service import db
from odds_service.config import get_settings
from odds_service.oddspapi import OddsPapiClient, OddsPapiError, with_team_names

# Gap between calls, to stay under OddsPapi's per-endpoint burst limit.
DELAY_S = 1.0

MARKET_FIELDS = ("marketName", "marketType", "period", "handicap")


def add_market_names(fixtures: list[dict[str, Any]], markets: dict[str, dict[str, Any]]) -> None:
    """Annotate fixtures in place; ids unknown to /markets are left as-is."""
    for fixture in fixtures:
        # Fixtures without prices come back with no bookmakerOdds/markets key.
        for bookmaker in fixture.get("bookmakerOdds", {}).values():
            for market_id, market in bookmaker.get("markets", {}).items():
                if not (info := markets.get(market_id)):
                    continue
                market.update({k: info[k] for k in MARKET_FIELDS})
                names = {str(o["outcomeId"]): o["outcomeName"] for o in info["outcomes"]}
                for outcome_id, outcome in market["outcomes"].items():
                    if outcome_id in names:
                        outcome["outcomeName"] = names[outcome_id]


def backfill_names(path: Path, names: dict[str, str]) -> str:
    saved = json.loads(path.read_text())
    if not names or all(f.get("participant1Name") for f in saved["fixtures"]):
        return "skipped"
    saved["fixtures"] = [with_team_names(f, names) for f in saved["fixtures"]]
    path.write_text(json.dumps(saved, indent=1))
    return "team names added"


def starts_on(fixture: dict[str, Any], day: date) -> bool:
    # startTime is UTC ("2026-09-30T16:00:00.000Z"); compare in local time.
    start = datetime.fromisoformat(fixture["startTime"].replace("Z", "+00:00"))
    return start.astimezone().date() == day


async def export(sport_id: int, bookmaker: str, out_root: Path, day: date) -> None:
    settings = get_settings()
    conn = db.connect(settings.database_url) if settings.database_url else None
    async with httpx.AsyncClient(
        base_url=settings.oddspapi_base_url, timeout=settings.http_timeout
    ) as http:
        client = OddsPapiClient(http, settings.oddspapi_key.get_secret_value())

        sport = next(s for s in await client.sports() if s["sportId"] == sport_id)
        tournaments = [
            t
            for t in await client.tournaments(sport_id)
            if t["upcomingFixtures"] or t["liveFixtures"]
        ]
        # Keys in odds responses are strings, so index the definitions the same way.
        markets = {str(m["marketId"]): m for m in await client.markets(sport_id)}
        try:
            names = await client.participants(sport_id)
        except OddsPapiError as exc:
            names = {}
            print(f"team names unavailable ({exc.detail}); saving without them")
        out_dir = out_root / bookmaker / sport["slug"]
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"{len(tournaments)} active {sport['sportName']} tournaments, {day} -> {out_dir}")

        total = 0
        for i, t in enumerate(tournaments, 1):
            label = f"[{i}/{len(tournaments)}] {t['tournamentId']} {t['tournamentName']}"
            path = out_dir / f"{day}-{t['tournamentId']}-{t['tournamentSlug']}.json"
            if path.exists():
                print(f"{label}: already saved, {backfill_names(path, names)}")
                continue
            await asyncio.sleep(DELAY_S)
            try:
                fixtures = await client.odds_by_tournaments([t["tournamentId"]], bookmaker)
            except OddsPapiError as exc:
                # 404 = the bookmaker doesn't price this tournament; nothing to save.
                reason = "no odds, skipped" if exc.status_code == 404 else f"error {exc.detail}"
                print(f"{label}: {reason}")
                continue
            fixtures = [f for f in fixtures if starts_on(f, day)]
            if not fixtures:
                print(f"{label}: no fixtures on {day}, skipped")
                continue
            add_market_names(fixtures, markets)
            fixtures = [with_team_names(f, names) for f in fixtures]
            path.write_text(json.dumps({"tournament": t, "fixtures": fixtures}, indent=1))
            total += len(fixtures)
            saved = ""
            if conn is not None:
                _, n_odds = db.save_fixtures(conn, fixtures, t["tournamentName"])
                saved = f", {n_odds} odds saved to Postgres"
            print(f"{label}: {len(fixtures)} fixtures{saved}")

        print(f"done: {total} fixtures")
    if conn is not None:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sport-id", type=int, default=10, help="10 = soccer")
    parser.add_argument("--bookmaker", default="betpawa.cm")
    parser.add_argument("--out", type=Path, default=get_settings().odds_data_dir)
    parser.add_argument("--date", type=date.fromisoformat, default=date.today(), help="yyyy-mm-dd")
    args = parser.parse_args()
    asyncio.run(export(args.sport_id, args.bookmaker, args.out, args.date))


if __name__ == "__main__":
    main()
