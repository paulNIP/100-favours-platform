"""Load exported odds JSON files into Postgres (costs no OddsPapi quota).

    uv run odds-import-json [data/odds]        # from the repo root; needs DATABASE_URL

Safe to re-run: fixtures are upserted and each fixture's odds replaced.
"""

import json
import sys
from pathlib import Path

from odds_service import db
from odds_service.config import get_settings


def main() -> None:
    settings = get_settings()
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else settings.odds_data_dir
    url = settings.database_url
    if not url:
        raise SystemExit("set DATABASE_URL")

    files = sorted(root.rglob("*.json"))
    fixtures = odds = 0
    with db.connect(url) as conn:
        for path in files:
            saved = json.loads(path.read_text())
            n_fixtures, n_odds = db.save_fixtures(
                conn, saved["fixtures"], saved.get("tournament", {}).get("tournamentName")
            )
            fixtures += n_fixtures
            odds += n_odds
            print(f"{path.relative_to(root)}: {n_fixtures} fixtures, {n_odds} odds")
    print(f"done: {len(files)} files, {fixtures} fixtures, {odds} odds")


if __name__ == "__main__":
    main()
