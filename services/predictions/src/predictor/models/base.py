from collections.abc import Callable
from typing import Protocol, Self

import numpy as np
import pandas as pd

from ..markets.scorelines import MAX_GOALS


class GoalModel(Protocol):
    """What every model provides. Grids in, so markets/calibration/value are shared.

    fit() gets played matches in the canonical schema (predictor.data.schema);
    predict_grids() gets fixtures in the same schema and returns an (n, G, G) array
    where [k, i, j] = P(fixture k ends home i - away j).
    """

    name: str

    def fit(self, matches: pd.DataFrame) -> Self: ...

    def predict_grids(self, fixtures: pd.DataFrame) -> np.ndarray: ...


class PerLeague:
    """One model per league.

    Teams in different leagues never meet, so their ratings aren't comparable in one
    fit. It's also the natural unit to scale out: leagues train independently.
    """

    def __init__(self, factory: Callable[[], GoalModel], name: str):
        self.factory = factory
        self.name = name
        self.models: dict[str, GoalModel] = {}

    def fit(self, matches: pd.DataFrame) -> Self:
        self.models = {
            league: self.factory().fit(group) for league, group in matches.groupby("league")
        }
        return self

    def predict_grids(self, fixtures: pd.DataFrame) -> np.ndarray:
        grids = np.empty((len(fixtures), MAX_GOALS + 1, MAX_GOALS + 1))
        for league, positions in fixtures.groupby("league").indices.items():
            if league not in self.models:
                raise ValueError(f"no model trained for league {league!r}")
            grids[positions] = self.models[league].predict_grids(fixtures.iloc[positions])
        return grids

    def __getstate__(self) -> dict:
        # The factory is often a lambda (not picklable) and isn't needed to predict.
        return {k: v for k, v in self.__dict__.items() if k != "factory"}
