from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field, SecretStr, model_validator
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
    gemini_model: str = "gemini-3.5-flash"
    llm_timeout_seconds: float = Field(default=14.0, gt=0, le=30)
    analysis_timeout_seconds: float = Field(default=30.0, gt=0, le=30)
    internal_auth_required: bool = False
    internal_api_key: Optional[SecretStr] = None
    chunk_size_tokens: int = Field(default=700, ge=100, le=2000)
    chunk_overlap_tokens: int = Field(default=100, ge=0, le=500)
    embedding_provider: Literal["fake", "e5"] = "fake"
    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_batch_size: int = Field(default=16, ge=1, le=128)
    database_url: Optional[SecretStr] = None
    vector_dimension: int = Field(default=768, ge=1, le=2000)
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    max_grounded_chunks: int = Field(default=15, ge=1, le=25)
    existing_experience_match_distance: float = Field(default=0.4, ge=0, le=2)
    max_related_experiences: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def validate_chunk_window(self) -> "Settings":
        if self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ValueError("chunk overlap must be smaller than chunk size")
        if (
            self.llm_provider == "gemini"
            and self.llm_timeout_seconds * 2 >= self.analysis_timeout_seconds
        ):
            raise ValueError(
                "analysis timeout must allow two LLM attempts within the total limit"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
