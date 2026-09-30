"""Walk-forward backtest; also fits and saves the calibrator the predict step uses.

uv run predict-backtest --model dixon_coles --leagues E0 --test-seasons 2023 2024
"""

import argparse
import json
from datetime import UTC, datetime

from predictor.config import get_settings
from predictor.data.store import MatchStore
from predictor.evaluation.backtest import evaluate, simulate_bets, walk_forward
from predictor.markets.scorelines import markets, poisson_grid
from predictor.models import MODELS
from predictor.models.calibration import MarketCalibrator
from predictor.models.registry import ModelRegistry


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=settings.model_name, choices=MODELS)
    parser.add_argument("--leagues", nargs="+", required=True)
    parser.add_argument("--test-seasons", nargs="+", type=int, required=True)
    parser.add_argument("--refit-days", type=int, default=30)
    parser.add_argument("--min-ev", type=float, default=0.02)
    args = parser.parse_args()

    matches = MatchStore(settings.data_dir / "matches").read(args.leagues)
    predictions = walk_forward(matches, MODELS[args.model], args.test_seasons, args.refit_days)
    report = evaluate(predictions) | {"betting": simulate_bets(predictions, args.min_ev)}

    # Out-of-sample predictions are exactly what calibration must be fitted on.
    market_names = [m for m in markets(poisson_grid(1.4, 1.1)) if m in predictions]
    calibrator = MarketCalibrator().fit(predictions, market_names)
    ModelRegistry(settings.models_dir).save(
        calibrator,
        f"{args.model}-calibrator",
        {
            "leagues": args.leagues,
            "test_seasons": args.test_seasons,
            "markets": len(calibrator.models),
        },
    )

    out = settings.artifacts_dir / "backtests"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    predictions.to_parquet(out / f"{args.model}-{stamp}.parquet")
    (out / f"{args.model}-{stamp}.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
