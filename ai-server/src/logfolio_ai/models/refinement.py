from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import Field

from logfolio_ai.models.analysis import (
    AnalysisResponse,
    Evidence,
    ExistingExperience,
    GapQuestion,
    ProjectContext,
    SourceWarning,
    UserAnswer,
    UserCorrection,
)
from logfolio_ai.models.base import ContractModel
from logfolio_ai.models.enums import InformationNeedType
from logfolio_ai.models.usage import AIUsageRecord


class RefinementStatus(str, Enum):
    REVIEW_READY = "REVIEW_READY"
    NO_UPDATE = "NO_UPDATE"
    NEEDS_ADDITIONAL_SOURCE = "NEEDS_ADDITIONAL_SOURCE"


class ExperienceRefinementRequest(ContractModel):
    """Spring-owned review session input for refining one existing Experience."""

    review_session_id: UUID
    project_id: UUID
    source_ids: List[UUID] = Field(min_length=1, max_length=50)
    experience: ExistingExperience
    project_context: Optional[ProjectContext] = None
    corrections: List[UserCorrection] = Field(default_factory=list, max_length=100)
    answers: List[UserAnswer] = Field(default_factory=list, max_length=100)


class RefinementReviewItem(ContractModel):
    item_type: str = Field(min_length=1)
    original_content: Optional[str] = None
    proposed_content: str = Field(min_length=1)
    evidences: List[Evidence] = Field(default_factory=list)
    requires_user_confirmation: bool = False
    conflict: bool = False
    conflict_reason: Optional[str] = None


class ExperienceRefinementResponse(ContractModel):
    review_session_id: UUID
    project_id: UUID
    experience_id: UUID
    status: RefinementStatus
    summary: str = Field(min_length=1)
    review_items: List[RefinementReviewItem] = Field(default_factory=list, max_length=20)
    questions: List[GapQuestion] = Field(default_factory=list, max_length=2)
    source_warnings: List[SourceWarning] = Field(default_factory=list, max_length=50)
    no_update_reason: Optional[str] = None
    ai_usage: Optional[AIUsageRecord] = None


def refinement_response(
    request: ExperienceRefinementRequest,
    analysis: AnalysisResponse,
) -> ExperienceRefinementResponse:
    """Adapt the project analysis result without persisting Spring-owned review state."""

    target_id = request.experience.experience_id
    candidates = [
        candidate
        for candidate in analysis.candidates
        if candidate.target_experience_id == target_id
    ]
    candidate_ids = {candidate.candidate_id for candidate in candidates}
    existing = {
        claim.section_type.upper(): claim.content
        for claim in request.experience.claims
    }

    items: list[RefinementReviewItem] = []
    for candidate in candidates:
        conflicts = {
            detail.section_type.upper(): detail for detail in candidate.conflicts
        }
        for claim in candidate.claims:
            section = claim.section_type.upper()
            original = existing.get(section)
            if original is not None and _normalized(original) == _normalized(claim.content):
                continue
            conflict = conflicts.get(section)
            items.append(
                RefinementReviewItem(
                    item_type=claim.section_type,
                    original_content=original,
                    proposed_content=claim.content,
                    evidences=claim.evidences,
                    requires_user_confirmation=claim.requires_user_confirmation,
                    conflict=conflict is not None,
                    conflict_reason=conflict.reason if conflict is not None else None,
                )
            )

    questions = [
        question
        for question in analysis.questions
        if question.candidate_id is None or question.candidate_id in candidate_ids
    ]
    if items or questions:
        status = RefinementStatus.REVIEW_READY
    elif analysis.information_need == InformationNeedType.ADDITIONAL_SOURCE:
        status = RefinementStatus.NEEDS_ADDITIONAL_SOURCE
    else:
        status = RefinementStatus.NO_UPDATE

    reason = analysis.information_need_reason or analysis.no_update_reason
    if status == RefinementStatus.NO_UPDATE and reason is None:
        reason = "기존 경험에 반영할 새로운 근거 기반 제안이 없습니다."

    return ExperienceRefinementResponse(
        review_session_id=request.review_session_id,
        project_id=request.project_id,
        experience_id=target_id,
        status=status,
        summary=analysis.summary,
        review_items=items,
        questions=questions,
        source_warnings=analysis.source_warnings,
        no_update_reason=reason,
        ai_usage=analysis.ai_usage,
    )


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()
