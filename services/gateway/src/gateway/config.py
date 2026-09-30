from functools import lru_cache

from platform_common import ServiceSettings


class Settings(ServiceSettings):
    # Service registry, e.g. SERVICES='{"odds": "http://odds-service:8000"}'.
    # Adding a microservice = add a container + one entry here.
    services: dict[str, str] = {
        "odds": "http://127.0.0.1:8001",
        "notifications": "http://127.0.0.1:8002",
        "predictions": "http://127.0.0.1:8003",
    }
    upstream_timeout: float = 15.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
