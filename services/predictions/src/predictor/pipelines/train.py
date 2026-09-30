"""Fit a model on stored matches and save it as a new registry version.

uv run predict-train --model dixon_coles --leagues E0 E1 SP1
"""

import argparse

from predictor.config import get_settings
from predictor.data import football_data
from predictor.data.store import MatchStore
from predictor.models import MODELS, build_model
from predictor.models.registry import ModelRegistry


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=settings.model_name, choices=MODELS)
    parser.add_argument("--leagues", nargs="+", required=True)
    parser.add_argument(
        "--seasons", type=int, default=4, help="train on this many most recent seasons"
    )
    args = parser.parse_args()

    min_season = football_data.current_season() - args.seasons + 1
    matches = MatchStore(settings.data_dir / "matches").read(args.leagues, min_season)
    played = matches.dropna(subset=["home_goals", "away_goals"])
    model = build_model(args.model).fit(played)

    version = ModelRegistry(settings.models_dir).save(
        model,
        args.model,
        {
            "leagues": sorted(played.league.unique()),
            "matches": len(played),
            "trained_until": played.date.max().date().isoformat(),
        },
    )
    print(f"{args.model} {version}: {len(played)} matches, {played.league.nunique()} leagues")


if __name__ == "__main__":
    main()
