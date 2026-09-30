from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """Base for every service's settings: environment variables, then the repo's .env.

    Commands run from the repo root (see the Makefile), so ".env" is the shared one.
    In containers, docker-compose passes each service only the variables it needs.
    """

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", protected_namespaces=("settings_",)
    )
