from fastapi import HTTPException

from app.services.errors import WalletServiceError


def raise_http_error(exc: WalletServiceError) -> None:
    raise HTTPException(
        status_code=exc.http_status,
        detail={"code": exc.code, "message": exc.message},
    ) from exc
