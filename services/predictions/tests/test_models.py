import numpy as np
import pandas as pd
import pytest
from predictor.evaluation.backtest import evaluate, simulate_bets, walk_forward
from predictor.evaluation.metrics import brier, log_loss, rps
from predictor.features.build import build_features
from predictor.features.ratings import elo_ratings
from predictor.features.rolling import rolling_form
from predictor.models import MODELS, build_model
from predictor.models.calibration import MarketCalibrator
from predictor.models.dixon_coles import DixonColes
from predictor.models.registry import ModelRegistry


def test_elo_is_pre_match_and_moves_with_results():
    m = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-08", "2024-01-15"]),
            "home_team": ["A", "A", "B"],
            "away_team": ["B", "C", "A"],
            "home_goals": [3.0, 1.0, np.nan],
            "away_goals": [0.0, 1.0, np.nan],
        }
    )
    elo = elo_ratings(m)
    assert elo.loc[0, "elo_home"] == elo.loc[0, "elo_away"] == 1500  # nothing known yet
    assert elo.loc[1, "elo_home"] > 1500  # A won match 0
    assert elo.loc[2, "elo_away"] < elo.loc[1, "elo_home"]  # A drew at home vs weaker-rated C
    assert elo.loc[2, "elo_home"] < 1500  # B lost match 0; fixture 2 has no result


def test_rolling_form_never_includes_the_match_itself():
    m = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-05", "2024-01-09"]),
            "home_team": ["A", "B", "A"],
            "away_team": ["B", "A", "B"],
            "home_goals": [4.0, 0.0, 9.0],
            "away_goals": [0.0, 2.0, 9.0],
        }
    )
    form = rolling_form(m, windows=(5,))
    assert np.isnan(form.loc[0, "home_gf_last5"])
    assert form.loc[1, "away_gf_last5"] == 4.0  # A's first match only
    assert form.loc[2, "home_gf_last5"] == 3.0  # mean(4, 2); the 9 isn't included
    assert form.loc[2, "home_rest_days"] == 4


def test_dixon_coles_recovers_team_strengths(matches):
    model = DixonColes().fit(matches)
    attack = dict(zip(model.teams, model.attack))
    assert max(attack, key=attack.get) == "Strong"
    assert min(attack, key=attack.get) in ("Poor", "Weak")
    fixture = pd.DataFrame({"home_team": ["Strong"], "away_team": ["Poor"]})
    grid = model.predict_grids(fixture)[0]
    assert grid.sum() == pytest.approx(1)
    home_win = np.tril(grid, -1).sum()
    assert home_win > 0.6


def test_features_align_with_matches(matches):
    features = build_features(matches)
    assert features.index.equals(matches.index)
    assert {"elo_diff", "home_pts_last5", "mkt_home"} <= set(features.columns)


@pytest.mark.parametrize("name", list(MODELS))
def test_every_model_trains_predicts_and_round_trips(name, matches, tmp_path):
    model = build_model(name).fit(matches)
    fixtures = matches.tail(3).assign(home_goals=np.nan, away_goals=np.nan)
    grids = model.predict_grids(fixtures)
    assert grids.shape == (3, 11, 11)
    assert np.allclose(grids.sum(axis=(1, 2)), 1)

    registry = ModelRegistry(tmp_path)
    registry.save(model, name, {"leagues": ["X1"]})
    loaded, meta = registry.load(name)
    assert meta["leagues"] == ["X1"]
    assert np.allclose(loaded.predict_grids(fixtures), grids)


def test_walk_forward_only_trains_on_the_past(matches):
    seen_until = []

    class Spy(DixonColes):
        def fit(self, train):
            seen_until.append(train.date.max())
            return super().fit(train)

    preds = walk_forward(matches, Spy, test_seasons=[2023], refit_days=30)
    assert len(preds) == (matches.season == 2023).sum()
    assert max(seen_until) < preds.date.max()
    assert all(d < matches[matches.season == 2023].date.max() for d in seen_until)

    report = evaluate(preds)
    assert 0 < report["model"]["rps"] < 0.5
    assert report["with_odds"]["matches"] == len(preds)
    betting = simulate_bets(preds, min_ev=0.0)
    assert betting["bets"] >= 0


def test_calibrator_keeps_books_normalised(matches):
    preds = walk_forward(matches, DixonColes, test_seasons=[2022, 2023], refit_days=60)
    calibrator = MarketCalibrator(min_samples=30).fit(preds, ["home", "draw", "away"])
    out = calibrator.transform({"home": 0.5, "draw": 0.3, "away": 0.2, "btts_yes": 0.4})
    assert out["home"] + out["draw"] + out["away"] == pytest.approx(1)
    assert out["btts_yes"] == 0.4  # not calibrated -> untouched


def test_metrics():
    perfect = np.array([[1.0, 0, 0], [0, 0, 1.0]])
    assert log_loss(perfect, [0, 2]) == pytest.approx(0, abs=1e-9)
    assert brier(perfect, [0, 2]) == 0
    uniform = np.full((1, 3), 1 / 3)
    assert rps(uniform, [0]) == pytest.approx(((2 / 3) ** 2 + (1 / 3) ** 2) / 2)
    # Predicting draw when home won beats predicting away (RPS respects order).
    assert rps([[0, 1, 0]], [0]) < rps([[0, 0, 1]], [0])
