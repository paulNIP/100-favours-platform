# 100-favours platform

A FastAPI microservices monorepo. An API **gateway** routes `/api/<service>/...` to
independent services, which share one library and one lockfile:

| Service | Package | Does |
|---|---|---|
| [gateway](services/gateway) | `gateway` | reverse proxy, the only public port (:8000) |
| [odds](services/odds) | `odds_service` | wraps the [OddsPapi](https://oddspapi.io/us/docs) v4 API; stores fixtures and odds in Postgres |
| [notifications](services/notifications) | `notification_service` | Telegram messages and named templates |
| [predictions](services/predictions) | `prediction_service`, `predictor` | soccer market probabilities and value bets ([README](services/predictions/README.md)) |

```
client ──► gateway :8000 ─┬─► odds-service (N replicas) ──► api.oddspapi.io
                          │      ├──► redis (shared cache)
                          │      └──► postgres (fixtures, odds)
                          ├─► notification-service ──► api.telegram.org
                          └─► prediction-service ◄── pipelines (ingest/train/backtest/predict)
```

## Repository layout

```
.
├── pyproject.toml            # uv workspace: members, dev tools, pytest + ruff config
├── uv.lock                   # one lockfile for every service
├── Makefile                  # install, test, lint, dev servers, docker
├── docker-compose.yml
├── .env.example
├── libs/
│   └── common/               # platform-common, shared by every service
│       └── src/platform_common/
│           ├── app.py        # create_app(): FastAPI + GET /health + error handler
│           ├── errors.py     # UpstreamError -> JSON {"detail"} with the right status
│           └── settings.py   # ServiceSettings: env vars, then the repo's .env
├── services/
│   ├── gateway/
│   ├── odds/
│   │   ├── src/odds_service/
│   │   │   ├── main.py       # create_app + lifespan (HTTP client, cache, DB pool)
│   │   │   ├── config.py
│   │   │   ├── dependencies.py
│   │   │   ├── routers/      # reference.py, live.py (OddsPapi), stored.py (Postgres)
│   │   │   ├── oddspapi.py   # OddsPapi client
│   │   │   ├── cache.py      # memory / Redis cache with request coalescing
│   │   │   ├── db.py         # schema + writes
│   │   │   ├── repository.py # reads: fixtures with nested markets and odds
│   │   │   └── scripts/      # odds-export, odds-import-json
│   │   ├── tests/
│   │   └── docs/
│   ├── notifications/        # src/notification_service/{main,routes,telegram,templates,config}.py
│   └── predictions/          # src/predictor (ML library + pipelines), src/prediction_service (API)
├── data/                     # generated, git-ignored: data/odds, data/predictions
└── artifacts/                # generated, git-ignored: artifacts/predictions (models, picks)
```

Each service is its own package, with its own `pyproject.toml`, `Dockerfile` and
`tests/`, and depends only on `platform-common`, never on another service. Services
talk to each other over HTTP (the predict pipeline calls notification-service).

## Quick start

Requires [uv](https://docs.astral.sh/uv/) and Docker.

```bash
cp .env.example .env     # fill in ODDSPAPI_KEY, TELEGRAM_BOT_TOKEN, POSTGRES_PASSWORD, DATABASE_URL
make install             # one .venv at the root with every service and the dev tools
make test                # all services' tests
make up                  # build and start everything in Docker (gateway on :8000)
```

`make help` lists every target. Run commands from the repo root: settings read `.env`
from the working directory, and `data/` and `artifacts/` paths are relative to it.

### Local development without Docker

```bash
make db             # only Postgres, on 127.0.0.1:5433 (5432 is often taken locally)
make dev-odds       # :8001   each with --reload, in its own terminal
make dev-notifications  # :8002
make dev-predictions    # :8003
make dev-gateway    # :8000, routes to the three above
```

Interactive API docs: `http://127.0.0.1:<port>/docs` for each service.

### Tests and lint

- `make test` runs each service's suite separately; each service has its own `tests` package.
- Postgres integration tests run when `TEST_DATABASE_URL` is set. The Makefile derives it
  from `DATABASE_URL` (database `odds_test`); `make db-test` creates that database.
- `make lint` checks with ruff; `make format` fixes and formats.

## Endpoints (through the gateway)

### odds

| Route | Source | Cache |
|---|---|---|
| `GET /api/odds/v1/sports` | OddsPapi `/sports` | 24h |
| `GET /api/odds/v1/bookmakers` | `/bookmakers` | 24h |
| `GET /api/odds/v1/tournaments?sport_id=10` | `/tournaments` | 24h |
| `GET /api/odds/v1/participants?sport_id=10` | `/participants` (team id → name) | 24h |
| `GET /api/odds/v1/odds/{fixture_id}` | `/odds?fixtureId=` | 15s |
| `GET /api/odds/v1/odds?tournament_ids=17&tournament_ids=8&bookmaker=pinnacle` | `/odds-by-tournaments` | 15s |
| `GET /api/odds/v1/fixtures` | Postgres | – |
| `GET /api/odds/v1/fixtures/{fixture_id}` | Postgres | – |

- **Team names:** fixtures from `/v1/odds` include `participant1Name` / `participant2Name`
  next to the ids. They are null if the name lookup fails (for example when the quota is
  used up); the odds are still returned.
- **Stored fixtures:** `/v1/fixtures` returns each match (teams, tournament, kick-off) with
  `bookmakers[] → markets[] (name, type, period, handicap) → outcomes[] (name, price)`,
  ordered by kick-off and paginated (`limit` ≤ 200, `offset`).
- **Filters and defaults:**
  - `bookmaker`: `betpawa.cm` by default; `all` for every bookmaker.
  - `market_type`: every type by default; or one, e.g. `1x2`, `totals`.
  - `saved_on`: `today` by default; `yyyy-mm-dd`, or `all` for everything stored.
  - `date`: kick-off day. `date` and `saved_on` use `tz` (default `UTC`, e.g. `Africa/Douala`).
  - `tournament_id`.

### notifications

| Route | Does |
|---|---|
| `POST /api/notifications/v1/telegram/messages` | send `text` (`chat_id` falls back to `TELEGRAM_DEFAULT_CHAT_ID`) |
| `GET /api/notifications/v1/telegram/templates` | template names and the variables each needs |
| `POST /api/notifications/v1/telegram/templates/{name}` | render a template and send it |

```bash
curl -X POST localhost:8000/api/notifications/v1/telegram/templates/quiz \
  -H 'content-type: application/json' \
  -d '{"variables": {"question": "Which market id is Full Time Result?", "answer": "101"}}'
# 201 {"chat_id": "5166562888", "message_id": 42}
```

- **Templates:** `welcome`, `announcement`, `trading_signal`, `trade_update`,
  `daily_report`, `order_confirmation`, `reminder`, `service_down`, `help`, `quiz`.
- **Variables:** plain text, HTML-escaped for you. Missing or unknown variables return 422.
- **Messages:** `text` is 1–4096 characters; `parse_mode` is `HTML` or `MarkdownV2`;
  `disable_notification` sends silently.
- **Errors:** 400/403 pass Telegram's reason through (e.g. "chat not found"); 429 after
  one automatic retry for waits of 3s or less; a bad token or anything else is 502.
- **Chats:** the bot can only post to a user who has started it, or a group or channel
  it has been added to.

### predictions

`POST /v1/markets`, `POST /v1/value`, `POST /v1/predict`, `GET /v1/picks` under
`/api/predictions`. See the [predictions README](services/predictions/README.md).

## Jobs

Batch jobs are console scripts installed with their service. Run them from the repo
root, or as one-off containers that share the service's volumes:

```bash
uv run odds-export --sport-id 10 --bookmaker betpawa.cm   # today's odds -> data/odds + Postgres
uv run odds-import-json                                   # exported JSON -> Postgres, no API calls
uv run predict-ingest --leagues E0 E1                     # also predict-train, -backtest, -run

docker compose run --rm odds-service odds-export
docker compose run --rm prediction-service predict-train --leagues E0 E1
```

- **odds-export:** saves only fixtures that start today. It skips tournaments already
  saved for the day, and also saves to Postgres when `DATABASE_URL` is set. Each run
  makes about 53 OddsPapi calls, so watch the quota.
- **Postgres:** `fixtures` has one upserted row per match. `odds` has one row per
  fixture, bookmaker, market, outcome and player, and each save replaces that
  fixture's odds for that bookmaker.
- **Querying:** `docker compose exec postgres psql -U odds -d odds`, or an IDE on
  `127.0.0.1:5433`.

## Configuration

Settings come from environment variables, then `.env` (see `.env.example`). In Docker,
`docker-compose.yml` passes each service only the variables it needs.

| Variable | Used by |
|---|---|
| `ODDSPAPI_KEY` | odds |
| `DATABASE_URL`, `POSTGRES_USER` / `_PASSWORD` / `_DB` | odds, postgres |
| `REDIS_URL` | odds (unset: in-process cache) |
| `DEFAULT_BOOKMAKER`, `ODDS_DATA_DIR` | odds (defaults `betpawa.cm`, `data/odds`) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_DEFAULT_CHAT_ID` | notifications |
| `DATA_DIR`, `ARTIFACTS_DIR`, `MODEL_NAME`, `NOTIFICATION_URL` | predictions |
| `SERVICES` | gateway: `{"name": "base url"}` registry |
| `WORKERS` | every service: uvicorn workers per container |

## Design notes

- **Secrets stay server-side.** Only odds-service holds `ODDSPAPI_KEY`, and only
  notification-service holds the bot token. Neither service is exposed outside the Docker
  network, and upstream errors are re-raised without URLs, which would contain the secrets.
- **Quota and scaling:**
  - A Redis cache is shared by all odds replicas, so scaling out doesn't multiply upstream calls.
  - Concurrent cache misses for the same key wait on one upstream call.
  - A batch endpoint fetches many fixtures per request.
  - OddsPapi's short burst limit is retried once.
- **Stateless services.** Each worker keeps one pooled HTTP client and a DB pool, so you
  can scale with `docker compose up --scale odds-service=3` and tune `WORKERS`.
- **Upstream errors map consistently** (`platform_common.UpstreamError`): the caller's
  mistakes pass through (404, or 400/403 for Telegram), rate limits stay 429, and a bad
  key or anything else becomes 502.

## Add a service

1. `mkdir -p services/<name>/src/<name>_service services/<name>/tests`.
2. Add a `pyproject.toml` depending on `platform-common` (copy one from another service),
   then run `uv sync --all-packages`.
3. Build the app with `platform_common.create_app(...)`, and settings with `ServiceSettings`.
4. Copy a service's `Dockerfile` and change the package and module names.
5. Add it to `docker-compose.yml`, to the gateway's `SERVICES`, and to `SERVICES` in the Makefile.
