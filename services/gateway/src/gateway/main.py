from contextlib import asynccontextmanager

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from platform_common import create_app

from .config import get_settings

# Hop-by-hop headers must not be forwarded by a proxy (RFC 9110 §7.6.1).
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}

router = APIRouter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(timeout=get_settings().upstream_timeout)
    yield
    await app.state.http.aclose()


@router.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(service: str, path: str, request: Request) -> Response:
    base = get_settings().services.get(service)
    if base is None:
        raise HTTPException(404, f"Unknown service '{service}'")

    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}
    try:
        upstream = await request.app.state.http.request(
            request.method,
            f"{base}/{path}",
            params=request.query_params,
            headers=headers,
            content=await request.body(),
        )
    except httpx.HTTPError:
        raise HTTPException(503, f"Service '{service}' unavailable") from None

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={k: v for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP},
    )


app = create_app("gateway", routers=[router], lifespan=lifespan)
