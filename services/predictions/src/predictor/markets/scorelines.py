"""Scoreline grids -> probabilities for every market.

A grid is a (G, G) array with grid[i, j] = P(home scores i, away scores j). Every
model produces grids, so one function prices 1X2, totals, BTTS, DNB and Asian
handicap consistently for all of them.
"""

import numpy as np
from scipy.stats import poisson

MAX_GOALS = 10
TOTAL_LINES = (0.5, 1.5, 2.5, 3.5, 4.5, 5.5)
AH_LINES = (-2.5, -1.5, -0.5, 0.5, 1.5, 2.5)  # half lines only: no pushes


def poisson_grid(
    home_xg: float, away_xg: float, rho: float = 0.0, max_goals: int = MAX_GOALS
) -> np.ndarray:
    """Independent Poissons, with the Dixon-Coles low-score correction when rho != 0."""
    goals = np.arange(max_goals + 1)
    grid = np.outer(poisson.pmf(goals, home_xg), poisson.pmf(goals, away_xg))
    if rho:
        grid[0, 0] *= 1 - home_xg * away_xg * rho
        grid[0, 1] *= 1 + home_xg * rho
        grid[1, 0] *= 1 + away_xg * rho
        grid[1, 1] *= 1 - rho
    return grid / grid.sum()  # also absorbs the mass beyond max_goals


def markets(grid: np.ndarray) -> dict[str, float]:
    home_goals, away_goals = np.indices(grid.shape)
    total = home_goals + away_goals
    margin = home_goals - away_goals

    home, draw, away = grid[margin > 0].sum(), grid[margin == 0].sum(), grid[margin < 0].sum()
    btts = grid[(home_goals > 0) & (away_goals > 0)].sum()
    probs = {
        "home": home,
        "draw": draw,
        "away": away,
        "home_or_draw": home + draw,
        "home_or_away": home + away,
        "draw_or_away": draw + away,
        "dnb_home": home / (home + away),
        "dnb_away": away / (home + away),
        "btts_yes": btts,
        "btts_no": 1 - btts,
    }
    for line in TOTAL_LINES:
        over = grid[total > line].sum()
        probs[f"over_{line}"] = over
        probs[f"under_{line}"] = 1 - over
    for line in AH_LINES:
        probs[f"ah_home_{line:+g}"] = grid[margin + line > 0].sum()
        probs[f"ah_away_{line:+g}"] = grid[margin - line < 0].sum()
    return {name: float(p) for name, p in probs.items()}


def market_groups() -> list[tuple[str, ...]]:
    """Sets of outcomes that are exhaustive and exclusive, i.e. one bookmaker book each.

    Used to remove the margin (devig) and to renormalise after calibration.
    """
    groups = [("home", "draw", "away"), ("dnb_home", "dnb_away"), ("btts_yes", "btts_no")]
    groups += [(f"over_{line}", f"under_{line}") for line in TOTAL_LINES]
    groups += [(f"ah_home_{line:+g}", f"ah_away_{-line:+g}") for line in AH_LINES]
    return groups


def outcome(market: str, home_goals: int, away_goals: int) -> int | None:
    """1 = won, 0 = lost, None = void (DNB on a draw) or a market we can't settle."""
    margin, total = home_goals - away_goals, home_goals + away_goals
    simple = {
        "home": margin > 0,
        "draw": margin == 0,
        "away": margin < 0,
        "home_or_draw": margin >= 0,
        "home_or_away": margin != 0,
        "draw_or_away": margin <= 0,
        "btts_yes": home_goals > 0 and away_goals > 0,
        "btts_no": not (home_goals > 0 and away_goals > 0),
    }
    if market in simple:
        return int(simple[market])
    if market in ("dnb_home", "dnb_away"):
        return None if margin == 0 else int((margin > 0) == (market == "dnb_home"))

    kind, _, line_text = market.rpartition("_")
    try:
        line = float(line_text)
    except ValueError:
        return None
    settle = {
        "over": total > line,
        "under": total < line,
        "ah_home": margin + line > 0,
        "ah_away": margin - line < 0,
    }
    return int(settle[kind]) if kind in settle else None
