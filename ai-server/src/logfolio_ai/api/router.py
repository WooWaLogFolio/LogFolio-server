from fastapi import APIRouter

from logfolio_ai.api.routes import analyses, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(analyses.router, prefix="/api/v1")
