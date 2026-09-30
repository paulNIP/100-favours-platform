# prediction-service

Soccer match probabilities for every market, and **value bets ranked by expected value**
(EV = model_prob × odds − 1, bet only when EV > 0), with fractional-Kelly stakes.

## Layout

```
services/predictions/
├── pyproject.toml          # package "prediction-service" (predictor + prediction_service)
├── src/
│   ├── predictor/          # the ML library: pure Python, no web code
│   │   ├── config.py       # paths + model name (env vars / .env)
│   │   ├── data/           # schema.py (canonical match table), football_data.py, store.py
│   │   ├── features/       # ratings.py (Elo), rolling.py (form), build.py (feature matrix)
│   │   ├── models/         # base.py (GoalModel + PerLeague), dixon_coles.py, gbm.py,
│   │   │                   # ensemble.py, calibration.py, registry.py, __init__.py (MODELS)
│   │   ├── markets/        # scorelines.py (grid -> every market, settlement), devig.py
│   │   ├── betting/        # value.py (EV, value finder), staking.py (fractional Kelly)
│   │   ├── evaluation/     # metrics.py (log loss, Brier, RPS, CLV), backtest.py
│   │   └── pipelines/      # batch jobs, one CLI each:
│   │                       #   ingest.py   -> predict-ingest   (download -> store)
│   │                       #   train.py    -> predict-train    (store -> model version)
│   │                       #   backtest.py -> predict-backtest (report + calibrator)
│   │                       #   predict.py  -> predict-run      (picks JSON + Telegram)
│   └── prediction_service/ # FastAPI: serves the latest model, no training
│       ├── main.py         # app + lifespan (loads model and calibrator)
│       └── routes.py       # /v1/markets, /v1/value, /v1/predict, /v1/picks
└── tests/                  # synthetic league with known strengths
```

**The one contract that keeps it modular:** every model returns scoreline grids,
`grid[i, j] = P(home i, away j)`. Markets, calibration, value finding and backtests
work on grids, so they don't change when you add or swap a model.

## Flow

```
ingest (daily) ──► data/predictions/matches/<league>/<season>.parquet
train  (weekly) ─► artifacts/predictions/models/<model>/<version>/
backtest (on change) ─► artifacts/predictions/backtests/*.json  +  <model>-calibrator version
predict (daily) ─► artifacts/predictions/picks/<date>.json, latest.json ──► Telegram
API ─────────────► loads latest model + calibrator at startup
```

From the repo root (paths above are relative to it; `DATA_DIR` / `ARTIFACTS_DIR` override):

```bash
uv run predict-ingest   --leagues E0 E1 EC --from-season 2020
uv run predict-backtest --model dixon_coles --leagues E0 E1 --test-seasons 2025
uv run predict-train    --model dixon_coles --leagues E0 E1 EC
uv run predict-run      --min-ev 0.02 [--notify]
make dev-predictions    # API on :8003
```

With Docker, the same commands run as one-off jobs sharing the service's volumes:
`docker compose run --rm prediction-service predict-train --leagues E0 E1`.

Models: `dixon_coles`, `lightgbm`, `ensemble` (`--model`, or `MODEL_NAME` for the API).

## API (via gateway: `/api/predictions/...`)

| Route | Does |
|---|---|
| `POST /v1/markets` `{home_xg, away_xg, rho?}` | every market's probability from expected goals |
| `POST /v1/value` `{probabilities, odds, min_ev?}` | value bets with EV, fair (devigged) prob and stake |
| `POST /v1/predict` `{league, home_team, away_team, odds?}` | latest model's probabilities + value bets |
| `GET /v1/picks` | output of the last `pipelines.predict` run |

## Scaling

- **Train and serve are separate.** Pipelines are batch jobs; API replicas are stateless
  and only read artifacts, so they scale horizontally. New model = new version; roll
  back by pinning an older one.
- **League is the partition.** Storage, training (`PerLeague`) and prediction all split by
  league, so leagues can be ingested and fitted in parallel (Airflow task per league).
- **Swappable backends behind small interfaces:** `MatchStore` (Parquet → Postgres),
  `ModelRegistry` (local disk → S3/GCS, or MLflow), `MODELS` (add a model = one entry).

## First results (2025/26, Premier League + Championship, 932 matches)

| | log loss | RPS | flat-stake ROI at EV > 2% |
|---|---|---|---|
| Pinnacle closing odds | **1.029** | **0.212** | – |
| Dixon-Coles | 1.053 | 0.219 | −6.9% (1,516 bets) |
| LightGBM | 1.051 | 0.218 | −10.7% (1,398 bets) |

Neither model beats the market yet, so **don't bet on these picks**. Big EVs in the output
right now mean the model is wrong, not that the odds are.

## Next steps

- Richer features: xG (Understat/FBref), lineups and injuries, fixture congestion, stakes.
- Calibrate per league (the calibrator is currently one per model, fitted on whichever
  leagues were backtested) and track closing-line value on live picks.
- Price the betPawa CM odds from odds-service. Their fixtures only carry participant IDs,
  so they need a team-name mapping to football-data names first.
- Postgres `MatchStore`, and an Airflow DAG wrapping the four pipelines.
