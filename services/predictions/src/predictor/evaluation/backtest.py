"""Walk-forward backtests: always train on the past, predict the future, in time order.

A random train/test split leaks future form into training and overstates skill.
"""

from collections.abc import Callable

import numpy as np
import pandas as pd

from ..betting.value import find_value
from ..data.schema import ODDS_COLUMNS
from ..markets.devig import devig
from ..markets.scorelines import markets, outcome
from ..models.base import GoalModel
from .metrics import score

RESULT = ["home", "draw", "away"]


def walk_forward(
    matches: pd.DataFrame,
    model_factory: Callable[[], GoalModel],
    test_seasons: list[int],
    refit_days: int = 30,
) -> pd.DataFrame:
    """Predict every match in test_seasons with a model trained only on earlier matches.

    The model is refitted every refit_days, the way it would be in production, so
    it learns from the season as it unfolds. Returns the test matches with one
    probability column per market.
    """
    chunks = []
    for season in test_seasons:
        test = matches[matches.season == season]
        start, last = test.date.min(), test.date.max()
        while start <= last:
            end = start + pd.Timedelta(days=refit_days)
            chunk = test[(test.date >= start) & (test.date < end)]
            train = matches[(matches.date < start) & matches.home_goals.notna()]
            if len(chunk) and len(train):
                grids = model_factory().fit(train).predict_grids(chunk)
                probs = pd.DataFrame([markets(g) for g in grids], index=chunk.index)
                chunks.append(chunk.join(probs))
            start = end
    if not chunks:
        raise ValueError(f"nothing to backtest for seasons {test_seasons} (need earlier data)")
    return pd.concat(chunks)


def result_index(predictions: pd.DataFrame) -> np.ndarray:
    margin = predictions.home_goals - predictions.away_goals
    return np.select([margin > 0, margin == 0], [0, 1], 2)


def evaluate(predictions: pd.DataFrame) -> dict:
    """1X2 scores for the model, and for the bookmaker on the same matches.

    If the model can't beat the margin-free odds, it has no edge to bet on.
    """
    y = result_index(predictions)
    report = {"matches": len(predictions), "model": score(predictions[RESULT].to_numpy(), y)}

    odds_columns = [ODDS_COLUMNS[m] for m in RESULT]
    if set(odds_columns) <= set(predictions.columns):
        has_odds = predictions[odds_columns].notna().all(axis=1).to_numpy()
        if has_odds.any():
            book = np.array([devig(r) for r in predictions.loc[has_odds, odds_columns].to_numpy()])
            report["with_odds"] = {
                "matches": int(has_odds.sum()),
                "model": score(predictions.loc[has_odds, RESULT].to_numpy(), y[has_odds]),
                "market": score(book, y[has_odds]),
            }
    return report


def simulate_bets(predictions: pd.DataFrame, min_ev: float = 0.0) -> dict:
    """Flat 1-unit stake on every value bet at the recorded odds."""
    staked = profit = wins = 0.0
    # to_dict, not itertuples: tuples rename columns like "over_2.5" that aren't identifiers.
    for row in predictions.to_dict("records"):
        odds = {
            m: row[c]
            for m, c in ODDS_COLUMNS.items()
            if c in row and pd.notna(row[c]) and row[c] > 1
        }
        probs = {m: row[m] for m in odds}
        for pick in find_value(probs, odds, min_ev=min_ev):
            result = outcome(pick.market, row["home_goals"], row["away_goals"])
            if result is None:
                continue
            staked += 1
            wins += result
            profit += pick.odds - 1 if result else -1
    return {
        "bets": int(staked),
        "hit_rate": wins / staked if staked else None,
        "profit_units": profit,
        "roi": profit / staked if staked else None,
    }
