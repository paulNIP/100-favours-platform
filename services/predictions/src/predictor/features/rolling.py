import numpy as np
import pandas as pd

STATS = ("gf", "ga", "pts")  # goals for, goals against, points


def rolling_form(matches: pd.DataFrame, windows: tuple[int, ...] = (5, 10)) -> pd.DataFrame:
    """Each team's average goals for/against and points over its last N matches,
    plus rest days, as of kick-off (shift(1): the match itself is never included).
    """
    sides = []
    for side, gf, ga, team in (
        ("home", "home_goals", "away_goals", "home_team"),
        ("away", "away_goals", "home_goals", "away_team"),
    ):
        sides.append(
            pd.DataFrame(
                {
                    "match": matches.index,
                    "date": matches["date"],
                    "team": matches[team],
                    "gf": matches[gf].astype(float),
                    "ga": matches[ga].astype(float),
                    "side": side,
                }
            )
        )
    long = pd.concat(sides, ignore_index=True).sort_values(["date", "match"], kind="stable")
    long["pts"] = np.select([long.gf > long.ga, long.gf == long.ga], [3.0, 1.0], 0.0)
    long.loc[long.gf.isna(), "pts"] = np.nan

    by_team = long.groupby("team", sort=False)
    features = []
    for window in windows:
        for stat in STATS:
            column = f"{stat}_last{window}"
            long[column] = by_team[stat].transform(
                lambda s, w=window: s.shift(1).rolling(w, min_periods=1).mean()
            )
            features.append(column)
    long["rest_days"] = by_team["date"].diff().dt.days
    features.append("rest_days")

    home, away = (
        long[long.side == side].set_index("match")[features].add_prefix(f"{side}_")
        for side in ("home", "away")
    )
    return home.join(away).reindex(matches.index)
