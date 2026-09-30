from collections.abc import Callable, Iterable
from contextlib import AbstractAsyncContextManager

from fastapi import APIRouter, FastAPI

from .errors import add_upstream_error_handler

Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_app(
    title: str, *, routers: Iterable[APIRouter] = (), lifespan: Lifespan | None = None
) -> FastAPI:
    """A FastAPI app with what every service shares: GET /health (for docker
    healthchecks) and UpstreamError -> JSON error responses."""
    app = FastAPI(title=title, lifespan=lifespan)

    @app.get("/health", tags=["ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    add_upstream_error_handler(app)
    for router in routers:
        app.include_router(router)
    return app
