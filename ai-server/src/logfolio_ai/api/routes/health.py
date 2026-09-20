from fastapi import APIRouter

from logfolio_ai.core.config import get_settings
from logfolio_ai.models.base import ContractModel

router = APIRouter(tags=["health"])


class HealthResponse(ContractModel):
    status: str
    service: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
