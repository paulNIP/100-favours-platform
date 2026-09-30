import numpy as np
import pandas as pd
import pytest
from predictor.markets.scorelines import markets, poisson_grid

# Known team strengths, so tests can check models recover them.
ATTACK = {"Strong": 0.45, "Good": 0.2, "Mid": 0.0, "Mid2": -0.05, "Weak": -0.25, "Poor": -0.35}
HOME_ADV = 0.25


def synthetic_matches(seasons: int = 4, seed: int = 0, margin: float = 0.05) -> pd.DataFrame:
    """Double round robin per season, goals ~ Poisson from ATTACK, odds with a margin."""
    rng = np.random.default_rng(seed)
    teams = list(ATTACK)
    rows = []
    for s in range(seasons):
        day = pd.Timestamp(f"{2020 + s}-08-01")
        for home in teams:
            for away in teams:
                if home == away:
                    continue
                lam = np.exp(HOME_ADV + ATTACK[home] - ATTACK[away])
                mu = np.exp(ATTACK[away] - ATTACK[home])
                p = markets(poisson_grid(lam, mu))
                rows.append(
                    {
                        "date": day,
                        "season": 2020 + s,
                        "league": "X1",
                        "home_team": home,
                        "away_team": away,
                        "home_goals": float(rng.poisson(lam)),
                        "away_goals": float(rng.poisson(mu)),
                        **{
                            f"odds_{m}": 1 / (p[m] * (1 + margin))
                            for m in ("home", "draw", "away", "over_2.5", "under_2.5")
                        },
                    }
                )
                day += pd.Timedelta(days=3)
    return pd.DataFrame(rows)


@pytest.fixture(scope="session")
def matches() -> pd.DataFrame:
    return synthetic_matches()
