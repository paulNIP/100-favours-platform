from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from platform_common import create_app

from .config import get_settings
from .routes import router
from .telegram import TelegramClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # One pooled client per worker process; reused across all requests.
    http = httpx.AsyncClient(base_url=settings.telegram_base_url, timeout=settings.http_timeout)
    app.state.telegram = TelegramClient(http, settings.telegram_bot_token.get_secret_value())
    yield
    await http.aclose()


app = create_app("notification-service", routers=[router], lifespan=lifespan)
