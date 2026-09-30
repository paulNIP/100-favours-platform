from collections.abc import Callable

from .base import GoalModel, PerLeague
from .dixon_coles import DixonColes
from .ensemble import Ensemble
from .gbm import GoalGBM

# Name -> factory for a fresh, untrained model. Pipelines and the API select by name,
# so adding a model = implement GoalModel + one entry here.
MODELS: dict[str, Callable[[], GoalModel]] = {
    "dixon_coles": lambda: PerLeague(DixonColes, "dixon_coles"),
    "lightgbm": lambda: PerLeague(GoalGBM, "lightgbm"),
    "ensemble": lambda: PerLeague(lambda: Ensemble([DixonColes(), GoalGBM()]), "ensemble"),
}


def build_model(name: str) -> GoalModel:
    if name not in MODELS:
        raise ValueError(f"unknown model {name!r}; choose from {', '.join(MODELS)}")
    return MODELS[name]()
