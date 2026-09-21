from typing import Protocol

from logfolio_ai.llm.models import GroundedAnalysisInput
from logfolio_ai.models import AnalysisResponse


class LLMProvider(Protocol):
    async def analyze_grounded(
        self, request: GroundedAnalysisInput
    ) -> AnalysisResponse:
        """Analyze only evidence chunks selected by the RAG pipeline."""
