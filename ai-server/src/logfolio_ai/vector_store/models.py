from typing import Optional
from uuid import UUID

from pydantic import Field

from logfolio_ai.models.base import ContractModel
from logfolio_ai.models.enums import SourceType


class VectorSearchResult(ContractModel):
    chunk_id: UUID
    source_id: UUID
    source_type: SourceType = SourceType.PROJECT_FILE
    source_name: str
    sequence: int = Field(ge=0)
    page_number: Optional[int] = Field(default=None, ge=1)
    section_title: Optional[str] = None
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    text: str = Field(min_length=1)
    distance: float = Field(ge=0)
