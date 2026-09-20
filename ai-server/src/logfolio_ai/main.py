import uvicorn
from fastapi import FastAPI

from logfolio_ai.api.router import api_router
from logfolio_ai.core.config import get_settings
from logfolio_ai.core.errors import register_exception_handlers


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Evidence-grounded project experience analysis API",
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "logfolio_ai.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "local",
    )
