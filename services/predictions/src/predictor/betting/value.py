from collections.abc import Mapping
from dataclasses import dataclass

from ..markets.devig import devig
from ..markets.scorelines import market_groups


@dataclass(frozen=True)
class Pick:
    market: str
    model_prob: float
    odds: float
    # Bookmaker's probability with its margin removed; None when we don't have the
    # whole book (e.g. only the "over" price), so the margin can't be taken out.
    fair_prob: float | None
    ev: float


def ev(prob: float, odds: float) -> float:
    """Expected profit per unit staked at decimal odds."""
    return prob * odds - 1


def find_value(
    model_probs: Mapping[str, float],
    odds: Mapping[str, float],
    min_ev: float = 0.0,
    min_prob: float = 0.0,
) -> list[Pick]:
    """Bets with EV above min_ev, most likely first.

    Filtering on EV first and then ranking by probability gives bets that both have
    an edge and win often, rather than short-priced "safe" bets that lose money.
    """
    fair: dict[str, float] = {}
    for group in market_groups():
        if all(m in odds for m in group):
            fair.update(zip(group, devig([odds[m] for m in group])))

    picks = [
        Pick(market, p, price, fair.get(market), ev(p, price))
        for market, price in odds.items()
        if (p := model_probs.get(market)) is not None
    ]
    value = [pick for pick in picks if pick.ev > min_ev and pick.model_prob >= min_prob]
    return sorted(value, key=lambda pick: (-pick.model_prob, -pick.ev))
