from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class UpstreamError(Exception):
    """A third-party API failed; status_code is what *our* caller should get.

    Services subclass it per upstream (OddsPapiError, TelegramError) and map the
    upstream's statuses: the caller's mistakes pass through (400/404), our own
    misconfiguration (bad key/token) becomes 502, and the detail never contains secrets.
    """

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def add_upstream_error_handler(app: FastAPI) -> None:
    @app.exception_handler(UpstreamError)
    async def handle(_: Request, exc: UpstreamError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
