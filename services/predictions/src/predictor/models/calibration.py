from typing import Self

import numpy as np
import pandas as pd

from ..markets.scorelines import market_groups, outcome


class MarketCalibrator:
    """Isotonic calibration per market, fitted on out-of-sample backtest predictions.

    EV is only as good as the probabilities, so this maps "model says 70%" to how
    often such bets actually won. Books (1X2, over/under...) are renormalised after,
    and outputs are kept inside [0.5%, 99.5%] so a sparse bucket can't claim certainty.
    """

    def __init__(self, min_samples: int = 300):
        self.min_samples = min_samples
        self.models: dict = {}

    def fit(self, predictions: pd.DataFrame, markets: list[str]) -> Self:
        from sklearn.isotonic import IsotonicRegression

        hg = predictions.home_goals.to_numpy()
        ag = predictions.away_goals.to_numpy()
        for market in markets:
            results = np.array([outcome(market, h, a) for h, a in zip(hg, ag)], dtype=object)
            settled = np.array([r is not None for r in results])
            if settled.sum() < self.min_samples:
                continue
            self.models[market] = IsotonicRegression(
                y_min=0.005, y_max=0.995, out_of_bounds="clip"
            ).fit(predictions[market].to_numpy()[settled], results[settled].astype(float))
        return self

    def transform(self, probs: dict[str, float]) -> dict[str, float]:
        out = {
            m: float(self.models[m].predict([p])[0]) if m in self.models else p
            for m, p in probs.items()
        }
        for group in market_groups():
            if all(m in out for m in group) and any(m in self.models for m in group):
                total = sum(out[m] for m in group)
                out.update({m: out[m] / total for m in group})
        return out
