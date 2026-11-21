from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentClient
from app.api.errors import raise_http_error
from app.db.session import get_db
from app.schemas.wallet import BalanceResponse, WalletCreateRequest, WalletResponse
from app.services.errors import WalletServiceError
from app.services.wallet_service import WalletService

router = APIRouter(prefix="/wallets", tags=["Wallets"])
DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=WalletResponse, status_code=status.HTTP_201_CREATED)
def create_wallet(
    payload: WalletCreateRequest,
    client: CurrentClient,
    db: DbSession,
) -> WalletResponse:
    try:
        wallet = WalletService(db).create_wallet(
            client_id=client.id,
            external_player_id=payload.external_player_id,
            currency=payload.currency,
        )
    except WalletServiceError as exc:
        raise_http_error(exc)
    return WalletResponse.model_validate(wallet, from_attributes=True)


@router.get("/{external_player_id}/balance", response_model=BalanceResponse)
def get_balance(
    external_player_id: str,
    client: CurrentClient,
    db: DbSession,
    currency: Annotated[str, Query(min_length=3, max_length=3)],
) -> BalanceResponse:
    try:
        wallet = WalletService(db).get_balance(
            client_id=client.id,
            external_player_id=external_player_id,
            currency=currency,
        )
    except WalletServiceError as exc:
        raise_http_error(exc)
    return BalanceResponse(
        wallet_id=wallet.id,
        player_id=wallet.player_id,
        currency=wallet.currency,
        balance=Decimal(wallet.balance),
    )
