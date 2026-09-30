from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from platform_common import create_app
from psycopg_pool import AsyncConnectionPool

from .cache import CachedLoader, MemoryCache, RedisCache
from .config import get_settings
from .db import SCHEMA
from .oddspapi import OddsPapiClient
from .routers import live, reference, stored


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # One pooled client per worker process; reused across all requests.
    http = httpx.AsyncClient(
        base_url=settings.oddspapi_base_url,
        timeout=settings.http_timeout,
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    cache = RedisCache(settings.redis_url) if settings.redis_url else MemoryCache()
    app.state.oddspapi = OddsPapiClient(http, settings.oddspapi_key.get_secret_value())
    app.state.loader = CachedLoader(cache)
    # Stored fixtures are optional: without DATABASE_URL the /v1/fixtures routes answer 503.
    app.state.db = None
    if settings.database_url:
        app.state.db = AsyncConnectionPool(
            settings.database_url, min_size=1, max_size=10, open=False
        )
        await app.state.db.open()
        async with app.state.db.connection() as conn:
            await conn.execute(SCHEMA)  # idempotent; lets the API start before any import
    yield
    await http.aclose()
    await cache.close()
    if app.state.db is not None:
        await app.state.db.close()


app = create_app(
    "odds-service", routers=[reference.router, live.router, stored.router], lifespan=lifespan
)
