from functools import lru_cache

from platform_common import ServiceSettings
from pydantic import SecretStr


class Settings(ServiceSettings):
    telegram_bot_token: SecretStr
    telegram_base_url: str = "https://api.telegram.org"
    # Used when a request doesn't name a chat, e.g. a team channel for alerts.
    telegram_default_chat_id: str | None = None
    http_timeout: float = 10.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
