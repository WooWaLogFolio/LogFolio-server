from enum import Enum
from typing import List
from uuid import UUID

from pydantic import Field

from logfolio_ai.chunking import DocumentChunk
from logfolio_ai.models.base import ContractModel
from logfolio_ai.vector_store import VectorSearchResult


class AnalysisPurpose(str, Enum):
    PROJECT_OVERVIEW = "PROJECT_OVERVIEW"
    USER_CONTRIBUTION = "USER_CONTRIBUTION"
    DECISION_REASON = "DECISION_REASON"
    OUTCOME = "OUTCOME"
    LEARNING = "LEARNING"


class IndexingResult(ContractModel):
    document_count: int = Field(ge=0)
    chunk_count: int = Field(ge=0)
    embedding_model: str


class RetrievalContext(ContractModel):
    purpose: AnalysisPurpose
    query: str
    chunks: List[VectorSearchResult] = Field(default_factory=list)


class ExistingExperienceContext(ContractModel):
    experience_id: UUID
    relevance_distance: float = Field(ge=0)
    chunks: List[DocumentChunk] = Field(default_factory=list)
