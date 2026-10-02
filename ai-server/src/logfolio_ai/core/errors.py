from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from logfolio_ai.models.base import ContractModel
from logfolio_ai.models.usage import AIUsageRecord


class ErrorItem(ContractModel):
    field: Optional[str] = None
    message: str
    type: str


class ErrorResponse(ContractModel):
    code: str
    message: str
    details: List[ErrorItem] = Field(default_factory=list)
    ai_usage: Optional[AIUsageRecord] = None


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Optional[List[ErrorItem]] = None,
        ai_usage: Optional[AIUsageRecord] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []
        self.ai_usage = ai_usage


def _response_content(payload: ErrorResponse) -> Dict[str, Any]:
    content = payload.model_dump(mode="json", by_alias=True)
    if payload.ai_usage is None:
        content.pop("aiUsage", None)
    return content


def _field_path(location: Any) -> Optional[str]:
    if not isinstance(location, (list, tuple)):
        return None
    parts = [str(part) for part in location if part not in {"body", "query", "path"}]
    return ".".join(parts) or None


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del request
        details = [
            ErrorItem(
                field=_field_path(error.get("loc")),
                message=error.get("msg", "Invalid value"),
                type=error.get("type", "validation_error"),
            )
            for error in exc.errors()
        ]
        payload = ErrorResponse(
            code="VALIDATION_ERROR",
            message="요청 값이 API 계약과 일치하지 않습니다.",
            details=details,
        )
        return JSONResponse(
            status_code=422,
            content=_response_content(payload),
        )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        del request
        payload = ErrorResponse(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            ai_usage=exc.ai_usage,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_response_content(payload),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        del request
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        message = (
            "요청한 API를 찾을 수 없습니다."
            if exc.status_code == 404
            else "HTTP 요청을 처리할 수 없습니다."
        )
        payload = ErrorResponse(code=code, message=message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_response_content(payload),
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        del request, exc
        payload = ErrorResponse(
            code="INTERNAL_SERVER_ERROR",
            message="서버 내부 오류가 발생했습니다.",
        )
        return JSONResponse(
            status_code=500,
            content=_response_content(payload),
        )
