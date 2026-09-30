import pandas as pd


def elo_ratings(
    matches: pd.DataFrame, k: float = 20.0, home_advantage: float = 60.0, initial: float = 1500.0
) -> pd.DataFrame:
    """Pre-match Elo for both teams: each row only reflects matches before it.

    Upcoming fixtures (NaN goals) get the latest ratings and don't update them.
    Goal-difference multiplier as in the World Football Elo ratings.
    """
    ratings: dict[str, float] = {}
    home_elo, away_elo = {}, {}
    for row in matches.sort_values("date", kind="stable").itertuples():
        rh = ratings.get(row.home_team, initial)
        ra = ratings.get(row.away_team, initial)
        home_elo[row.Index], away_elo[row.Index] = rh, ra
        if pd.isna(row.home_goals) or pd.isna(row.away_goals):
            continue

        expected = 1 / (1 + 10 ** ((ra - rh - home_advantage) / 400))
        score = (
            1.0
            if row.home_goals > row.away_goals
            else 0.5
            if row.home_goals == row.away_goals
            else 0.0
        )
        gd = abs(row.home_goals - row.away_goals)
        multiplier = 1.0 if gd <= 1 else 1.5 if gd == 2 else (11 + gd) / 8
        delta = k * multiplier * (score - expected)
        ratings[row.home_team] = rh + delta
        ratings[row.away_team] = ra - delta

    out = pd.DataFrame({"elo_home": pd.Series(home_elo), "elo_away": pd.Series(away_elo)})
    out = out.reindex(matches.index)
    out["elo_diff"] = out.elo_home - out.elo_away
    return out
