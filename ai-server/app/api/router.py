from fastapi import APIRouter

from app.core.config import settings
from app.schemas.models import (
    GenerateCardRequest,
    GenerateCardResponse,
    GenerateQuestionsRequest,
    GenerateQuestionsResponse,
    HealthResponse,
)
from app.services.ai_service import ai_service

api_router = APIRouter()
ai_router = APIRouter(prefix="/api/v1/ai", tags=["AI"])


@api_router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name)


@ai_router.post("/generate-questions", response_model=GenerateQuestionsResponse)
async def generate_questions(
    request: GenerateQuestionsRequest,
) -> GenerateQuestionsResponse:
    return await ai_service.generate_questions(request)


@ai_router.post("/generate-card", response_model=GenerateCardResponse)
async def generate_card(request: GenerateCardRequest) -> GenerateCardResponse:
    return await ai_service.generate_card(request)


api_router.include_router(ai_router)
