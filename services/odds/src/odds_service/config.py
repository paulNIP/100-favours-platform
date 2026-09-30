from functools import lru_cache
from pathlib import Path

from platform_common import ServiceSettings
from pydantic import SecretStr


class Settings(ServiceSettings):
    oddspapi_key: SecretStr
    oddspapi_base_url: str = "https://api.oddspapi.io/v4"
    http_timeout: float = 10.0

    # Unset -> in-process memory cache (fine for local dev, not shared across replicas).
    redis_url: str | None = None
    reference_ttl: int = 86_400  # sports / tournaments / bookmakers rarely change
    odds_ttl: int = 15

    # e.g. postgresql://odds:secret@postgres:5432/odds. Unset -> exports only write JSON.
    database_url: str | None = None
    # Bookmaker /v1/fixtures shows when the request doesn't name one ("all" = every bookmaker).
    default_bookmaker: str = "betpawa.cm"
    # Where scripts.export_odds writes JSON (relative to the repo root by default).
    odds_data_dir: Path = Path("data/odds")


@lru_cache
def get_settings() -> Settings:
    return Settings()
