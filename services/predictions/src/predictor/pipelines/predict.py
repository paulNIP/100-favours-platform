"""Price upcoming fixtures, write the value picks, optionally send them to Telegram.

    uv run predict-run --min-ev 0.02 --notify

Writes artifacts/picks/<yyyy-mm-dd>.json and latest.json (served by GET /v1/picks).
"""

import argparse
import html
import json
from datetime import date

import httpx
import pandas as pd

from predictor.betting.staking import stake_fraction
from predictor.betting.value import find_value
from predictor.config import get_settings
from predictor.data import football_data
from predictor.data.schema import ODDS_COLUMNS
from predictor.markets.scorelines import markets
from predictor.models.registry import ModelRegistry

MAX_TELEGRAM_PICKS = 15  # keeps the message well under Telegram's 4096 chars


def value_picks(model, fixtures: pd.DataFrame, min_ev: float, calibrator=None) -> list[dict]:
    picks = []
    for fixture, grid in zip(fixtures.to_dict("records"), model.predict_grids(fixtures)):
        probs = markets(grid)
        if calibrator is not None:
            probs = calibrator.transform(probs)
        odds = {m: fixture[c] for m, c in ODDS_COLUMNS.items() if pd.notna(fixture.get(c))}
        for pick in find_value(probs, odds, min_ev=min_ev):
            picks.append(
                {
                    "date": fixture["date"].date().isoformat(),
                    "league": fixture["league"],
                    "home_team": fixture["home_team"],
                    "away_team": fixture["away_team"],
                    "market": pick.market,
                    "model_prob": round(pick.model_prob, 4),
                    "fair_prob": None if pick.fair_prob is None else round(pick.fair_prob, 4),
                    "odds": pick.odds,
                    "ev": round(pick.ev, 4),
                    "stake_fraction": round(stake_fraction(pick.model_prob, pick.odds), 4),
                }
            )
    return sorted(picks, key=lambda p: (-p["model_prob"], -p["ev"]))


def telegram_text(picks: list[dict], day: date) -> str:
    lines = [f"🎯 <b>Value picks — {day.isoformat()}</b>", ""]
    for p in picks[:MAX_TELEGRAM_PICKS]:
        fair = f" vs fair {p['fair_prob']:.0%}" if p["fair_prob"] is not None else ""
        lines += [
            f"⚽ <b>{html.escape(p['home_team'])} vs {html.escape(p['away_team'])}</b>"
            f" ({html.escape(p['league'])}, {p['date']})",
            f"   {html.escape(p['market'])}: model {p['model_prob']:.0%}{fair}"
            f" @ <code>{p['odds']:.2f}</code> → EV <b>{p['ev']:+.1%}</b>",
        ]
    if len(picks) > MAX_TELEGRAM_PICKS:
        lines.append(f"\n…and {len(picks) - MAX_TELEGRAM_PICKS} more")
    lines.append("\n⚠️ <i>Not financial advice. Manage your risk.</i>")
    return "\n".join(lines)


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=settings.model_name)
    parser.add_argument("--min-ev", type=float, default=0.02)
    parser.add_argument("--notify", action="store_true", help="send picks via notification-service")
    args = parser.parse_args()

    registry = ModelRegistry(settings.models_dir)
    model, meta = registry.load(args.model)
    try:
        calibrator, _ = registry.load(f"{args.model}-calibrator")
    except FileNotFoundError:
        calibrator = None
        print("no calibrator yet (run pipelines.backtest): using raw model probabilities")

    fixtures = football_data.load_fixtures()
    # The feed can still list matches from the last day or two; they've been played.
    upcoming = fixtures.date >= pd.Timestamp(date.today())
    fixtures = fixtures[upcoming & fixtures.league.isin(meta["leagues"])].reset_index(drop=True)
    picks = value_picks(model, fixtures, args.min_ev, calibrator) if len(fixtures) else []

    today = date.today()
    settings.picks_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "date": today.isoformat(),
            "model": meta["name"],
            "version": meta["version"],
            "picks": picks,
        },
        indent=1,
    )
    (settings.picks_dir / f"{today.isoformat()}.json").write_text(payload)
    (settings.picks_dir / "latest.json").write_text(payload)
    print(f"{len(fixtures)} fixtures -> {len(picks)} value picks")

    if args.notify and picks:
        if not settings.notification_url:
            raise SystemExit("--notify needs NOTIFICATION_URL")
        res = httpx.post(
            f"{settings.notification_url}/v1/telegram/messages",
            json={"text": telegram_text(picks, today), "parse_mode": "HTML"},
            timeout=15,
        )
        res.raise_for_status()
        print(f"sent to Telegram: message {res.json()['message_id']}")


if __name__ == "__main__":
    main()
