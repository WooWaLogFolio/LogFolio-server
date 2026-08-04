from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="LogFolio 질문 생성 및 경험 카드 구조화 API",
    )
    application.include_router(api_router)
    return application


app = create_app()
