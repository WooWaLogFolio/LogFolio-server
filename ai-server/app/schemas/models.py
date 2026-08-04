from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RecordInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(description="메인 백엔드 기록 식별자")
    content: str = Field(min_length=1, max_length=10_000, description="기록 본문")
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=20)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


class ContextType(StrEnum):
    ROLE = "role"
    PROBLEM = "problem"
    PROCESS = "process"
    COLLABORATION = "collaboration"
    RESULT = "result"
    LEARNING = "learning"
    EVIDENCE = "evidence"


class GenerateQuestionsRequest(BaseModel):
    records: list[RecordInput] = Field(min_length=1, max_length=20)


class GeneratedQuestion(BaseModel):
    context_type: ContextType = Field(serialization_alias="contextType")
    question: str


class GenerateQuestionsResponse(BaseModel):
    questions: list[GeneratedQuestion] = Field(min_length=1, max_length=2)


class QuestionAnswer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=1_000)
    answer: str = Field(min_length=1, max_length=10_000)


class GenerateCardRequest(BaseModel):
    records: list[RecordInput] = Field(min_length=1, max_length=20)
    answers: list[QuestionAnswer] = Field(default_factory=list, max_length=10)


class ExperienceCard(BaseModel):
    title: str
    role: str | None = None
    problem: str | None = None
    actions: list[str] = Field(default_factory=list)
    collaboration: str | None = None
    result: str | None = None
    learning: str | None = None
    evidence: list[str] = Field(default_factory=list)
    missing_contexts: list[str] = Field(default_factory=list, serialization_alias="missingContexts")


class GenerateCardResponse(BaseModel):
    card: ExperienceCard
