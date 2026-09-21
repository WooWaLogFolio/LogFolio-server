from typing import Protocol

from logfolio_ai.models import AnalysisRequest, AnalysisResponse


class LLMProvider(Protocol):
    async def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        """Return a response that satisfies the shared Spring contract."""

