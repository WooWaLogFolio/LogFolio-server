from uuid import uuid4

import pytest
from pydantic import ValidationError

from logfolio_ai.chunking import chunk_documents
from logfolio_ai.core.config import Settings
from logfolio_ai.models import DocumentPage, DocumentSource


def document(text: str, *, page_number: int = 1) -> DocumentSource:
    return DocumentSource(
        source_id=uuid4(),
        source_name="project.md",
        pages=[DocumentPage(page_number=page_number, text=text)],
    )


def test_short_document_preserves_exact_source_metadata() -> None:
    source = document("# 인증 기능\nJWT 인증 API를 구현했다.")

    chunks = chunk_documents([source], chunk_size_tokens=20, overlap_tokens=5)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.source_id == source.source_id
    assert chunk.source_name == "project.md"
    assert chunk.page_number == 1
    assert chunk.section_title == "인증 기능"
    assert chunk.text == source.pages[0].text
    assert source.pages[0].text[chunk.char_start : chunk.char_end] == chunk.text


def test_long_document_uses_configured_overlap() -> None:
    words = [f"token{index}" for index in range(10)]
    source = document(" ".join(words))

    chunks = chunk_documents([source], chunk_size_tokens=6, overlap_tokens=2)

    assert [chunk.token_count for chunk in chunks] == [6, 6]
    assert chunks[0].text.split()[-2:] == chunks[1].text.split()[:2]
    assert chunks[0].sequence == 0
    assert chunks[1].sequence == 1


def test_chunk_ids_are_stable_for_the_same_source() -> None:
    source = document("동일한 문서는 동일한 식별자를 사용한다.")

    first = chunk_documents([source], chunk_size_tokens=10, overlap_tokens=2)
    second = chunk_documents([source], chunk_size_tokens=10, overlap_tokens=2)

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]


def test_pages_are_not_mixed_into_one_chunk() -> None:
    source = DocumentSource(
        source_id=uuid4(),
        source_name="project.pdf",
        pages=[
            DocumentPage(page_number=1, text="첫 번째 페이지"),
            DocumentPage(page_number=2, text="두 번째 페이지"),
        ],
    )

    chunks = chunk_documents([source], chunk_size_tokens=20, overlap_tokens=5)

    assert [chunk.page_number for chunk in chunks] == [1, 2]
    assert [chunk.sequence for chunk in chunks] == [0, 1]


@pytest.mark.parametrize(
    ("size", "overlap"),
    [(0, 0), (10, -1), (10, 10), (10, 11)],
)
def test_invalid_chunk_window_is_rejected(size: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        chunk_documents([], chunk_size_tokens=size, overlap_tokens=overlap)


def test_settings_reject_overlap_equal_to_chunk_size() -> None:
    with pytest.raises(ValidationError):
        Settings(chunk_size_tokens=100, chunk_overlap_tokens=100)
