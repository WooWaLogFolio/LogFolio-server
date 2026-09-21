import secrets
from typing import Optional

from fastapi import Depends, Header

from logfolio_ai.core.config import Settings, get_settings
from logfolio_ai.core.errors import AppError


def require_internal_api_key(
    x_internal_api_key: Optional[str] = Header(
        default=None,
        alias="X-Internal-API-Key",
    ),
    settings: Settings = Depends(get_settings),
) -> None:
    configured_key = (
        settings.internal_api_key.get_secret_value()
        if settings.internal_api_key is not None
        else ""
    )

    if not configured_key:
        must_authenticate = settings.internal_auth_required or settings.environment not in {
            "local",
            "test",
        }
        if must_authenticate:
            raise AppError(
                code="INTERNAL_AUTH_NOT_CONFIGURED",
                message="내부 API 인증 키가 서버에 설정되지 않았습니다.",
                status_code=500,
            )
        return

    if x_internal_api_key is None or not secrets.compare_digest(
        x_internal_api_key,
        configured_key,
    ):
        raise AppError(
            code="INTERNAL_AUTH_FAILED",
            message="내부 API 인증에 실패했습니다.",
            status_code=401,
        )
