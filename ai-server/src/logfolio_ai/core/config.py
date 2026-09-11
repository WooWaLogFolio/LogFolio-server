from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="LOGFOLIO_AI_",
        extra="ignore",
    )

    app_name: str = "LogFolio AI Server"
    app_version: str = "0.1.0"
    environment: str = "local"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)


@lru_cache
def get_settings() -> Settings:
    return Settings()
