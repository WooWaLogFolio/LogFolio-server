from typing import List, Optional
from uuid import UUID

from pydantic import Field

from logfolio_ai.models.base import ContractModel
from logfolio_ai.rag.models import AnalysisPurpose


class GroundedChunk(ContractModel):
    chunk_id: UUID
    source_id: UUID
    file_name: str
    page_number: Optional[int] = Field(default=None, ge=1)
    section_title: Optional[str] = None
    text: str = Field(min_length=1)
    distance: float = Field(ge=0)
    purposes: List[AnalysisPurpose] = Field(min_length=1)


class GroundedAnalysisInput(ContractModel):
    analysis_run_id: UUID
    project_id: UUID
    chunks: List[GroundedChunk] = Field(default_factory=list, max_length=25)
