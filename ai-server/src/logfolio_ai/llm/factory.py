from functools import lru_cache

from logfolio_ai.core.config import Settings, get_settings
from logfolio_ai.core.errors import AppError
from logfolio_ai.llm.fake import FakeLLMProvider
from logfolio_ai.llm.gemini import GeminiLLMProvider
from logfolio_ai.llm.protocol import LLMProvider


def build_llm_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "fake":
        return FakeLLMProvider()

    if (
        settings.gemini_api_key is None
        or not settings.gemini_api_key.get_secret_value().strip()
    ):
        raise AppError(
            code="LLM_CONFIGURATION_ERROR",
            message="Gemini 사용을 위한 API 키가 설정되지 않았습니다.",
            status_code=500,
        )

    return GeminiLLMProvider(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


@lru_cache
def get_llm_provider() -> LLMProvider:
    return build_llm_provider(get_settings())
