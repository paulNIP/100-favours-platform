from functools import lru_cache
from pathlib import Path

from platform_common import ServiceSettings


class Settings(ServiceSettings):
    # Relative to the repo root by default; containers set absolute paths on volumes.
    data_dir: Path = Path("data/predictions")  # ingested matches
    artifacts_dir: Path = Path("artifacts/predictions")  # models, backtests, picks
    # Which trained model the API and predict pipeline use (see predictor.models.MODELS).
    model_name: str = "dixon_coles"
    # notification-service base URL; unset -> predict pipeline doesn't send to Telegram.
    notification_url: str | None = None

    @property
    def models_dir(self) -> Path:
        return self.artifacts_dir / "models"

    @property
    def picks_dir(self) -> Path:
        return self.artifacts_dir / "picks"


@lru_cache
def get_settings() -> Settings:
    return Settings()
