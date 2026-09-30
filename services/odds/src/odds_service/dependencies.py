"""Per-request dependencies. The objects live on app.state (created in main.lifespan)."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from psycopg import AsyncConnection

from .cache import CachedLoader
from .config import Settings, get_settings
from .oddspapi import OddsPapiClient


def get_client(request: Request) -> OddsPapiClient:
    return request.app.state.oddspapi


def get_loader(request: Request) -> CachedLoader:
    return request.app.state.loader


async def get_db(request: Request) -> AsyncIterator[AsyncConnection]:
    pool = request.app.state.db
    if pool is None:
        raise HTTPException(503, "No database configured (set DATABASE_URL)")
    async with pool.connection() as conn:
        yield conn


Client = Annotated[OddsPapiClient, Depends(get_client)]
Loader = Annotated[CachedLoader, Depends(get_loader)]
Db = Annotated[AsyncConnection, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]
