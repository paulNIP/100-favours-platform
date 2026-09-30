from typing import Self

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

from ..markets.scorelines import MAX_GOALS, poisson_grid


class DixonColes:
    """Dixon & Coles (1997): per-team attack/defence Poisson with a low-score correction.

    home_xg = exp(home_adv + attack[home] + defence[away])
    away_xg = exp(attack[away] + defence[home])
    Older matches are down-weighted by exp(-xi * days_ago); xi=0.0019 gives a
    ~1-year half-life. Teams it hasn't seen (e.g. promoted) get league-average
    ratings, which usually overrates them.
    """

    name = "dixon_coles"

    def __init__(self, xi: float = 0.0019, max_goals: int = MAX_GOALS):
        self.xi = xi
        self.max_goals = max_goals

    def fit(self, matches: pd.DataFrame) -> Self:
        played = matches.dropna(subset=["home_goals", "away_goals"])
        self.teams = sorted(set(played.home_team) | set(played.away_team))
        index = {team: i for i, team in enumerate(self.teams)}
        h = played.home_team.map(index).to_numpy()
        a = played.away_team.map(index).to_numpy()
        x = played.home_goals.to_numpy(dtype=int)
        y = played.away_goals.to_numpy(dtype=int)
        weights = np.exp(-self.xi * (played.date.max() - played.date).dt.days.to_numpy())
        n = len(self.teams)
        low = {
            (0, 0): (x == 0) & (y == 0),
            (0, 1): (x == 0) & (y == 1),
            (1, 0): (x == 1) & (y == 0),
            (1, 1): (x == 1) & (y == 1),
        }

        def nll(params: np.ndarray) -> float:
            attack, defence, home_adv, rho = self._unpack(params, n)
            lam = np.exp(home_adv + attack[h] + defence[a])
            mu = np.exp(attack[a] + defence[h])
            tau = np.ones_like(lam)
            tau[low[0, 0]] = 1 - lam[low[0, 0]] * mu[low[0, 0]] * rho
            tau[low[0, 1]] = 1 + lam[low[0, 1]] * rho
            tau[low[1, 0]] = 1 + mu[low[1, 0]] * rho
            tau[low[1, 1]] = 1 - rho
            ll = np.log(np.clip(tau, 1e-10, None)) + poisson.logpmf(x, lam) + poisson.logpmf(y, mu)
            return -np.sum(weights * ll)

        x0 = np.concatenate([np.zeros(2 * n), [0.25, -0.05]])
        bounds = [(None, None)] * (2 * n + 1) + [(-0.3, 0.3)]
        result = minimize(nll, x0, method="L-BFGS-B", bounds=bounds)
        self.attack, self.defence, self.home_adv, self.rho = self._unpack(result.x, n)
        self.converged = bool(result.success)
        return self

    @staticmethod
    def _unpack(params: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray, float, float]:
        attack = params[:n] - params[:n].mean()  # identifiability: attacks sum to zero
        return attack, params[n : 2 * n], params[2 * n], params[2 * n + 1]

    def expected_goals(self, fixtures: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        attack = dict(zip(self.teams, self.attack))
        defence = dict(zip(self.teams, self.defence))
        mean_defence = float(np.mean(self.defence))
        att_h = fixtures.home_team.map(attack).fillna(0.0).to_numpy()
        att_a = fixtures.away_team.map(attack).fillna(0.0).to_numpy()
        def_h = fixtures.home_team.map(defence).fillna(mean_defence).to_numpy()
        def_a = fixtures.away_team.map(defence).fillna(mean_defence).to_numpy()
        return np.exp(self.home_adv + att_h + def_a), np.exp(att_a + def_h)

    def predict_grids(self, fixtures: pd.DataFrame) -> np.ndarray:
        home_xg, away_xg = self.expected_goals(fixtures)
        return np.stack(
            [poisson_grid(h, a, self.rho, self.max_goals) for h, a in zip(home_xg, away_xg)]
        )
