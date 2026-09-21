from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, SecretStr
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
    llm_provider: Literal["fake", "gemini"] = "fake"
    gemini_api_key: Optional[SecretStr] = None
    gemini_model: str = "gemini-3.8-flash"
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=30)


@lru_cache
def get_settings() -> Settings:
    return Settings()
