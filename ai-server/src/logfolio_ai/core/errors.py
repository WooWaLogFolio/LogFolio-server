from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field

from logfolio_ai.models.base import ContractModel


class ErrorItem(ContractModel):
    field: Optional[str] = None
    message: str
    type: str


class ErrorResponse(ContractModel):
    code: str
    message: str
    details: List[ErrorItem] = Field(default_factory=list)


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Optional[List[ErrorItem]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []


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
            content=payload.model_dump(mode="json", by_alias=True),
        )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        del request
        payload = ErrorResponse(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(mode="json", by_alias=True),
        )
