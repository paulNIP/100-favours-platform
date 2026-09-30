from typing import Self

import numpy as np
import pandas as pd

from .base import GoalModel


class Ensemble:
    """Weighted average of the members' scoreline grids (still a valid distribution)."""

    name = "ensemble"

    def __init__(self, models: list[GoalModel], weights: list[float] | None = None):
        self.models = models
        weights = np.asarray(weights or [1.0] * len(models), dtype=float)
        self.weights = weights / weights.sum()

    def fit(self, matches: pd.DataFrame) -> Self:
        for model in self.models:
            model.fit(matches)
        return self

    def predict_grids(self, fixtures: pd.DataFrame) -> np.ndarray:
        return sum(w * m.predict_grids(fixtures) for w, m in zip(self.weights, self.models))
