"""Bookmaker odds -> fair probabilities, by removing the bookmaker's margin."""

from collections.abc import Sequence

import numpy as np
from scipy.optimize import brentq


def margin(odds: Sequence[float]) -> float:
    """Overround: 0.05 means the book's implied probabilities add up to 105%."""
    return float(np.sum(1 / np.asarray(odds, dtype=float)) - 1)


def devig(odds: Sequence[float], method: str = "proportional") -> list[float]:
    inv = 1 / np.asarray(odds, dtype=float)
    if method == "proportional":
        fair = inv / inv.sum()
    elif method == "power":
        # p_i = inv_i ** k with k set so they sum to 1. Takes more margin off longshots
        # than favourites, which matches how bookmakers actually shade prices.
        k = brentq(lambda k: np.sum(inv**k) - 1, 0.01, 50.0)
        fair = inv**k
    else:
        raise ValueError(f"unknown devig method {method!r}")
    return fair.tolist()
