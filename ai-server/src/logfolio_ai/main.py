import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI

from logfolio_ai.api.router import api_router
from logfolio_ai.core.config import Settings, get_settings
from logfolio_ai.core.errors import register_exception_handlers
from logfolio_ai.embedding import get_embedding_provider
from logfolio_ai.llm import get_llm_provider


async def prepare_runtime(settings: Settings) -> None:
    """Load heavyweight local models before the server becomes ready."""

    if settings.embedding_provider == "e5":
        provider = await asyncio.to_thread(get_embedding_provider)
        if provider.dimension != settings.vector_dimension:
            raise RuntimeError(
                "Embedding model dimension does not match LOGFOLIO_AI_VECTOR_DIMENSION"
            )
    if settings.llm_provider == "gemini":
        await asyncio.to_thread(get_llm_provider)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await prepare_runtime(get_settings())
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Evidence-grounded project experience analysis API",
        lifespan=lifespan,
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
