# Build from the repo root: docker build -f services/predictions/Dockerfile .
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv
# LightGBM needs OpenMP at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/srv/.venv PATH="/srv/.venv/bin:$PATH"
# The whole workspace is copied so uv can check the lockfile; only this
# service and its dependencies are installed.
COPY pyproject.toml uv.lock ./
COPY libs libs
COPY services services
RUN uv sync --frozen --no-dev --no-editable --package prediction-service
RUN useradd --create-home app && mkdir -p /srv/data /srv/artifacts && chown app /srv/data /srv/artifacts
USER app
EXPOSE 8000
CMD uvicorn prediction_service.main:app --host 0.0.0.0 --port 8000 --workers ${WORKERS:-1}
