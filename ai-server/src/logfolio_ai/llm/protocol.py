from typing import Optional, Protocol

from logfolio_ai.llm.models import GroundedAnalysisInput, LLMCallMetrics
from logfolio_ai.models import AnalysisResponse


class LLMProvider(Protocol):
    @property
    def last_call_metrics(self) -> Optional[LLMCallMetrics]:
        """Metrics for the most recently completed call, when available."""

    async def analyze_grounded(
        self, request: GroundedAnalysisInput
    ) -> AnalysisResponse:
        """Analyze only evidence chunks selected by the RAG pipeline."""
