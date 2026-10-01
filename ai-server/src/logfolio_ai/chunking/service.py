import hashlib
import re
from typing import Iterable, List, Optional, Tuple
from uuid import NAMESPACE_URL, UUID, uuid5

from logfolio_ai.chunking.models import DocumentChunk
from logfolio_ai.models import DocumentSource

_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
_MARKDOWN_HEADING = re.compile(r"^\s*#{1,6}\s+(.+?)\s*$")
_NUMBERED_HEADING = re.compile(r"^\s*\d+(?:\.\d+)*[.)]?\s+(.+?)\s*$")


def _token_spans(text: str) -> List[Tuple[int, int]]:
    return [(match.start(), match.end()) for match in _TOKEN_PATTERN.finditer(text)]


def _headings(text: str) -> List[Tuple[int, str]]:
    headings: List[Tuple[int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped_line = line.rstrip("\r\n")
        match = _MARKDOWN_HEADING.match(stripped_line)
        if match is None:
            match = _NUMBERED_HEADING.match(stripped_line)
        if match is not None:
            headings.append((offset, match.group(1).strip()))
        offset += len(line)
    return headings


def _section_at(headings: List[Tuple[int, str]], position: int) -> Optional[str]:
    current: Optional[str] = None
    for offset, title in headings:
        if offset > position:
            break
        current = title
    return current


def _stable_chunk_id(
    project_file_id: UUID,
    page_number: Optional[int],
    sequence: int,
    text: str,
) -> UUID:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    identity = f"logfolio:{project_file_id}:{page_number}:{sequence}:{digest}"
    return uuid5(NAMESPACE_URL, identity)


def chunk_documents(
    documents: Iterable[DocumentSource],
    *,
    chunk_size_tokens: int = 700,
    overlap_tokens: int = 100,
) -> List[DocumentChunk]:
    """Split pages into overlapping chunks while preserving exact source offsets.

    The lightweight token counter is deterministic but is not an LLM-specific tokenizer.
    Exact model token counts can be added later without changing the chunk contract.
    """

    if chunk_size_tokens <= 0:
        raise ValueError("chunk_size_tokens must be greater than zero")
    if overlap_tokens < 0 or overlap_tokens >= chunk_size_tokens:
        raise ValueError("overlap_tokens must be between zero and chunk size")

    chunks: List[DocumentChunk] = []
    for document in documents:
        sequence = 0
        for page in document.pages:
            spans = _token_spans(page.text)
            headings = _headings(page.text)
            start_token = 0

            while start_token < len(spans):
                end_token = min(start_token + chunk_size_tokens, len(spans))
                char_start = spans[start_token][0]
                char_end = spans[end_token - 1][1]
                chunk_text = page.text[char_start:char_end]
                chunks.append(
                    DocumentChunk(
                        chunk_id=_stable_chunk_id(
                            document.project_file_id,
                            page.page_number,
                            sequence,
                            chunk_text,
                        ),
                        project_file_id=document.project_file_id,
                        original_name=document.original_name,
                        sequence=sequence,
                        page_number=page.page_number,
                        section_title=_section_at(headings, char_start),
                        char_start=char_start,
                        char_end=char_end,
                        token_count=end_token - start_token,
                        text=chunk_text,
                    )
                )
                sequence += 1

                if end_token == len(spans):
                    break
                start_token = end_token - overlap_tokens

    return chunks
