import json

import pytest
from fastapi.testclient import TestClient
from prediction_service.main import app
from predictor.config import Settings, get_settings
from predictor.models import build_model
from predictor.models.registry import ModelRegistry


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = Settings(artifacts_dir=tmp_path, model_name="dixon_coles")
    monkeypatch.setattr("prediction_service.main.get_settings", lambda: settings)
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app), settings
    app.dependency_overrides.clear()


def test_markets_from_expected_goals(client):
    http, _ = client
    res = http.post("/v1/markets", json={"home_xg": 1.5, "away_xg": 1.0})
    assert res.status_code == 200
    probs = res.json()
    assert probs["home"] + probs["draw"] + probs["away"] == pytest.approx(1)


def test_value_returns_only_positive_ev_with_stakes(client):
    http, _ = client
    res = http.post(
        "/v1/value",
        json={
            "probabilities": {"over_1.5": 0.81, "under_1.5": 0.19},
            "odds": {"over_1.5": 1.30, "under_1.5": 3.40},
        },
    )
    assert res.status_code == 200
    [pick] = res.json()
    assert pick["market"] == "over_1.5" and pick["ev"] > 0 and 0 < pick["stake_fraction"] <= 0.05


def test_value_rejects_odds_of_one_or_less(client):
    http, _ = client
    res = http.post("/v1/value", json={"probabilities": {"home": 0.5}, "odds": {"home": 1.0}})
    assert res.status_code == 422


def test_predict_without_model_is_503(client):
    http, _ = client
    with http:  # runs lifespan: finds no artifacts
        res = http.post("/v1/predict", json={"league": "X1", "home_team": "A", "away_team": "B"})
    assert res.status_code == 503


def test_predict_uses_latest_trained_model(client, matches):
    http, settings = client
    ModelRegistry(settings.models_dir).save(build_model("dixon_coles").fit(matches), "dixon_coles")
    with http:
        res = http.post(
            "/v1/predict",
            json={
                "league": "X1",
                "home_team": "Strong",
                "away_team": "Poor",
                "odds": {"home": 1.9, "draw": 3.8, "away": 4.5},
            },
        )
        unknown = http.post(
            "/v1/predict", json={"league": "ZZ", "home_team": "A", "away_team": "B"}
        )
    assert res.status_code == 200
    body = res.json()
    assert body["model"]["name"] == "dixon_coles"
    assert body["probabilities"]["home"] > 0.6
    assert [p["market"] for p in body["picks"]] == ["home"]
    assert unknown.status_code == 422


def test_latest_picks(client):
    http, settings = client
    assert http.get("/v1/picks").status_code == 404
    settings.picks_dir.mkdir(parents=True)
    (settings.picks_dir / "latest.json").write_text(json.dumps({"picks": []}))
    assert http.get("/v1/picks").json() == {"picks": []}
