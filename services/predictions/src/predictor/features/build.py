import numpy as np
import pandas as pd

from ..markets.devig import devig
from .ratings import elo_ratings
from .rolling import rolling_form

MARKET_ODDS = ["odds_home", "odds_draw", "odds_away"]


def build_features(matches: pd.DataFrame) -> pd.DataFrame:
    """Model-ready features, one row per match, aligned with matches.index.

    Add new feature families here (xG, injuries, stakes...) as functions of the same
    shape: matches in, pre-match features out.
    """
    features = elo_ratings(matches).join(rolling_form(matches))
    return features.join(market_implied(matches))


def market_implied(matches: pd.DataFrame) -> pd.DataFrame:
    """Margin-free 1X2 probabilities from the odds: the strongest single predictor.

    At prediction time these must be odds that were available then (not closing
    odds from the future), or the backtest will look better than reality.
    """
    out = pd.DataFrame(np.nan, index=matches.index, columns=["mkt_home", "mkt_draw", "mkt_away"])
    if not set(MARKET_ODDS) <= set(matches.columns):
        return out
    odds = matches[MARKET_ODDS]
    complete = odds.notna().all(axis=1) & (odds > 1).all(axis=1)
    if complete.any():
        out.loc[complete] = np.array([devig(row) for row in odds[complete].to_numpy()])
    return out
