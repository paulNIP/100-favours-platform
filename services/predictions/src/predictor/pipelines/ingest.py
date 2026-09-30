"""Download results + odds into the match store. Idempotent: safe to run daily.

    uv run predict-ingest --leagues E0 E1 SP1 --from-season 2015

Past seasons are fetched once; the current season is refreshed every run.
"""

import argparse

from predictor.config import get_settings
from predictor.data import football_data
from predictor.data.store import MatchStore


def main() -> None:
    current = football_data.current_season()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--leagues", nargs="+", required=True, choices=football_data.LEAGUES)
    parser.add_argument("--from-season", type=int, default=current - 5, help="start year")
    parser.add_argument("--to-season", type=int, default=current)
    parser.add_argument("--refresh", action="store_true", help="re-download past seasons too")
    args = parser.parse_args()

    store = MatchStore(get_settings().data_dir / "matches")
    for league in args.leagues:
        for season in range(args.from_season, args.to_season + 1):
            if store.exists(league, season) and season != current and not args.refresh:
                print(f"{league} {season}: stored, skipped")
                continue
            try:
                matches = football_data.load_season(league, season)
            except Exception as exc:  # noqa: BLE001 - one missing file shouldn't stop the run
                print(f"{league} {season}: failed ({type(exc).__name__}: {exc})")
                continue
            store.write(matches, league, season)
            print(f"{league} {season}: {len(matches)} matches")


if __name__ == "__main__":
    main()
