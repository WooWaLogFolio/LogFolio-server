from typing import List, Optional
from uuid import UUID

from pydantic import Field

from logfolio_ai.models.base import ContractModel
from logfolio_ai.models.analysis import ExistingExperience, UserAnswer, UserCorrection
from logfolio_ai.models.enums import SourceType
from logfolio_ai.rag.models import AnalysisPurpose


class GroundedChunk(ContractModel):
    chunk_id: UUID
    source_id: UUID
    source_type: SourceType = SourceType.PROJECT_FILE
    source_name: str
    page_number: Optional[int] = Field(default=None, ge=1)
    section_title: Optional[str] = None
    text: str = Field(min_length=1)
    distance: float = Field(ge=0)
    purposes: List[AnalysisPurpose] = Field(default_factory=list)
    related_experience_ids: List[UUID] = Field(default_factory=list)
    retrieval_fallback: bool = False


class GroundedAnalysisInput(ContractModel):
    analysis_run_id: UUID
    project_id: UUID
    chunks: List[GroundedChunk] = Field(default_factory=list, max_length=25)
    existing_experiences: List[ExistingExperience] = Field(
        default_factory=list,
        max_length=100,
    )
    corrections: List[UserCorrection] = Field(default_factory=list, max_length=100)
    answers: List[UserAnswer] = Field(default_factory=list, max_length=100)


class LLMCallMetrics(ContractModel):
    provider: str
    model: str
    input_tokens: Optional[int] = Field(default=None, ge=0)
    cached_input_tokens: Optional[int] = Field(default=None, ge=0)
    output_tokens: Optional[int] = Field(default=None, ge=0)
    reasoning_tokens: Optional[int] = Field(default=None, ge=0)
    latency_ms: int = Field(ge=0)
    retry_count: int = Field(default=0, ge=0)
