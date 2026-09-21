from typing import Optional
from uuid import UUID

from pydantic import Field

from logfolio_ai.models.base import ContractModel


class DocumentChunk(ContractModel):
    chunk_id: UUID
    source_id: UUID
    file_name: str
    sequence: int = Field(ge=0)
    page_number: Optional[int] = Field(default=None, ge=1)
    section_title: Optional[str] = None
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    token_count: int = Field(gt=0)
    text: str = Field(min_length=1)
