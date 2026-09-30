from typing import Self

import numpy as np
import pandas as pd

from ..features.build import build_features
from ..markets.scorelines import MAX_GOALS, poisson_grid

DEFAULT_PARAMS = {
    "objective": "poisson",
    "n_estimators": 300,
    "learning_rate": 0.03,
    "num_leaves": 15,
    "min_child_samples": 50,
    "verbose": -1,
}


class GoalGBM:
    """LightGBM with a Poisson objective: one regressor each for home and away goals.

    Features are rolling/rating features, so predicting needs the match history;
    it's kept from fit() and fixtures are appended to it before building features.
    """

    name = "lightgbm"

    def __init__(self, params: dict | None = None, max_goals: int = MAX_GOALS):
        self.params = DEFAULT_PARAMS | (params or {})
        self.max_goals = max_goals

    def fit(self, matches: pd.DataFrame) -> Self:
        from lightgbm import LGBMRegressor  # heavy import; only when this model is used

        self.history = matches.reset_index(drop=True)
        played = self.history.home_goals.notna() & self.history.away_goals.notna()
        features = build_features(self.history)[played]
        self.feature_names = list(features.columns)
        self.home_model = LGBMRegressor(**self.params).fit(
            features, self.history.home_goals[played]
        )
        self.away_model = LGBMRegressor(**self.params).fit(
            features, self.history.away_goals[played]
        )
        return self

    def predict_grids(self, fixtures: pd.DataFrame) -> np.ndarray:
        combined = pd.concat([self.history, fixtures], ignore_index=True)
        features = build_features(combined).iloc[len(self.history) :][self.feature_names]
        home_xg = self.home_model.predict(features)
        away_xg = self.away_model.predict(features)
        return np.stack(
            [poisson_grid(h, a, max_goals=self.max_goals) for h, a in zip(home_xg, away_xg)]
        )
