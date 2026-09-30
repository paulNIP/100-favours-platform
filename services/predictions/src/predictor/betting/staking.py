def kelly_fraction(prob: float, odds: float) -> float:
    """Share of bankroll that maximises long-run growth; 0 when there's no edge."""
    return max((prob * odds - 1) / (odds - 1), 0.0)


def stake_fraction(prob: float, odds: float, fraction: float = 0.25, cap: float = 0.05) -> float:
    """Fractional (default quarter) Kelly, capped.

    Full Kelly assumes the probabilities are exact; ours are estimates, so scale
    down and cap to survive model error.
    """
    return min(kelly_fraction(prob, odds) * fraction, cap)
