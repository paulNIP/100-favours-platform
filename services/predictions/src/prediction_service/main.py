from contextlib import asynccontextmanager

from fastapi import FastAPI
from platform_common import create_app
from predictor.config import get_settings
from predictor.models.registry import ModelRegistry

from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Serving only reads artifacts; training runs in predictor.pipelines on its own
    # schedule. Restart (or roll out new replicas) to pick up a newly trained version.
    settings = get_settings()
    registry = ModelRegistry(settings.models_dir)
    app.state.model = app.state.meta = app.state.calibrator = None
    try:
        app.state.model, app.state.meta = registry.load(settings.model_name)
        app.state.calibrator, _ = registry.load(f"{settings.model_name}-calibrator")
    except FileNotFoundError:
        pass  # /v1/markets and /v1/value still work; /v1/predict answers 503
    yield


app = create_app("prediction-service", routers=[router], lifespan=lifespan)
