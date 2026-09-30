import datetime as dt
import json
from typing import Annotated, Any

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request
from predictor.betting.staking import stake_fraction
from predictor.betting.value import find_value
from predictor.config import Settings, get_settings
from predictor.markets.scorelines import markets, poisson_grid
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1", tags=["predictions"])
Config = Annotated[Settings, Depends(get_settings)]
Odds = dict[str, Annotated[float, Field(gt=1)]]


class MarketsRequest(BaseModel):
    home_xg: float = Field(gt=0, le=10)
    away_xg: float = Field(gt=0, le=10)
    rho: float = Field(0.0, ge=-0.3, le=0.3, description="Dixon-Coles low-score correction")


class ValueRequest(BaseModel):
    probabilities: dict[str, Annotated[float, Field(ge=0, le=1)]]
    odds: Odds
    min_ev: float = 0.0


class FixtureRequest(BaseModel):
    league: str
    home_team: str
    away_team: str
    date: dt.date | None = None
    odds: Odds = {}
    min_ev: float = 0.0


class PickOut(BaseModel):
    market: str
    model_prob: float
    fair_prob: float | None
    odds: float
    ev: float
    stake_fraction: float  # quarter Kelly, capped at 5% of bankroll


def picks_out(probs: dict[str, float], odds: dict[str, float], min_ev: float) -> list[PickOut]:
    return [
        PickOut(
            market=p.market,
            model_prob=p.model_prob,
            fair_prob=p.fair_prob,
            odds=p.odds,
            ev=p.ev,
            stake_fraction=stake_fraction(p.model_prob, p.odds),
        )
        for p in find_value(probs, odds, min_ev=min_ev)
    ]


@router.post("/markets")
async def market_probabilities(req: MarketsRequest) -> dict[str, float]:
    """Every market's probability from expected goals."""
    return markets(poisson_grid(req.home_xg, req.away_xg, req.rho))


@router.post("/value")
async def value(req: ValueRequest) -> list[PickOut]:
    """Value bets (EV > min_ev) given your probabilities and the bookmaker's odds."""
    return picks_out(req.probabilities, req.odds, req.min_ev)


@router.post("/predict")
async def predict(req: FixtureRequest, request: Request) -> dict[str, Any]:
    model, meta = request.app.state.model, request.app.state.meta
    if model is None:
        raise HTTPException(503, "no trained model (run pipelines.train)")
    fixture = pd.DataFrame(
        [
            {
                "date": pd.Timestamp(req.date or dt.date.today()),
                "league": req.league,
                "home_team": req.home_team,
                "away_team": req.away_team,
                "home_goals": float("nan"),
                "away_goals": float("nan"),
            }
        ]
    )
    try:
        grid = model.predict_grids(fixture)[0]
    except ValueError as exc:  # league the model wasn't trained on
        raise HTTPException(422, str(exc)) from None
    probs = markets(grid)
    if request.app.state.calibrator is not None:
        probs = request.app.state.calibrator.transform(probs)
    return {
        "model": {"name": meta["name"], "version": meta["version"]},
        "probabilities": probs,
        "picks": picks_out(probs, req.odds, req.min_ev),
    }


@router.get("/picks")
async def latest_picks(cfg: Config) -> dict[str, Any]:
    """Output of the last pipelines.predict run."""
    path = cfg.picks_dir / "latest.json"
    if not path.exists():
        raise HTTPException(404, "no picks yet (run pipelines.predict)")
    return json.loads(path.read_text())
