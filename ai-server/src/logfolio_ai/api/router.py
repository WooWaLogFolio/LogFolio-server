from fastapi import APIRouter

from logfolio_ai.api.routes import analyses, health, sources

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(analyses.router, prefix="/api/v1")
api_router.include_router(sources.router, prefix="/api/v1")
api_router.include_router(sources.index_lifecycle_router, prefix="/api/v1")
