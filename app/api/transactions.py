from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentClient
from app.api.errors import raise_http_error
from app.core.redis import get_redis_lock_manager
from app.db.session import get_db
from app.schemas.transaction import (
    AdjustmentRequest,
    CreditRequest,
    DebitRequest,
    RefundRequest,
    RollbackRequest,
    TransactionHistoryResponse,
    TransactionResponse,
)
from app.services.errors import WalletServiceError
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["Transactions"])
DbSession = Annotated[Session, Depends(get_db)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=150)]


def _run(call: Any) -> TransactionResponse:
    try:
        result = call()
    except WalletServiceError as exc:
        raise_http_error(exc)
    return TransactionResponse.model_validate(result)


@router.post("/debit", response_model=TransactionResponse)
def debit(payload: DebitRequest, client: CurrentClient, db: DbSession, key: IdempotencyKey):
    return _run(lambda: TransactionService(db, lock_manager=get_redis_lock_manager()).debit(
        client_id=client.id, idempotency_key=key,
        external_player_id=payload.external_player_id, amount=payload.amount,
        currency=payload.currency, provider_reference=payload.provider_reference,
        provider_code=payload.provider_code, game_external_id=payload.game_external_id,
    ))


@router.post("/credit", response_model=TransactionResponse)
def credit(payload: CreditRequest, client: CurrentClient, db: DbSession, key: IdempotencyKey):
    return _run(lambda: TransactionService(db, lock_manager=get_redis_lock_manager()).credit(
        client_id=client.id, idempotency_key=key,
        external_player_id=payload.external_player_id, amount=payload.amount,
        currency=payload.currency, provider_reference=payload.provider_reference,
        provider_code=payload.provider_code, game_external_id=payload.game_external_id,
    ))


@router.post("/refund", response_model=TransactionResponse)
def refund(payload: RefundRequest, client: CurrentClient, db: DbSession, key: IdempotencyKey):
    return _run(lambda: TransactionService(db, lock_manager=get_redis_lock_manager()).refund(
        client_id=client.id, idempotency_key=key,
        external_player_id=payload.external_player_id,
        original_transaction_uuid=str(payload.original_transaction_uuid),
        amount=payload.amount, currency=payload.currency,
        provider_reference=payload.provider_reference,
    ))


@router.post("/rollback", response_model=TransactionResponse)
def rollback(payload: RollbackRequest, client: CurrentClient, db: DbSession, key: IdempotencyKey):
    return _run(lambda: TransactionService(db, lock_manager=get_redis_lock_manager()).rollback(
        client_id=client.id, idempotency_key=key,
        external_player_id=payload.external_player_id,
        original_transaction_uuid=str(payload.original_transaction_uuid),
        currency=payload.currency, provider_reference=payload.provider_reference,
    ))


@router.post("/adjustment", response_model=TransactionResponse)
def adjustment(payload: AdjustmentRequest, client: CurrentClient, db: DbSession, key: IdempotencyKey):
    return _run(lambda: TransactionService(db, lock_manager=get_redis_lock_manager()).adjust(
        client_id=client.id, idempotency_key=key,
        external_player_id=payload.external_player_id, amount=payload.amount,
        currency=payload.currency, direction=payload.direction.value,
        reason=payload.reason,
    ))

@router.get("/{external_player_id}/history", response_model=TransactionHistoryResponse)
def transaction_history(
    external_player_id: str,
    client: CurrentClient,
    db: DbSession,
    currency: Annotated[str, Query(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TransactionHistoryResponse:
    try:
        result = TransactionService(db).get_history(
            client_id=client.id,
            external_player_id=external_player_id,
            currency=currency,
            offset=offset,
            limit=limit,
        )
    except WalletServiceError as exc:
        raise_http_error(exc)
    return TransactionHistoryResponse.model_validate(result)

