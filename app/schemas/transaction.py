from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from app.schemas.common import (
    APIModel,
    CurrencyCode,
    PositiveAmount,
)


class TransactionType(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
    REFUND = "REFUND"
    ROLLBACK = "ROLLBACK"
    ADJUSTMENT = "ADJUSTMENT"


class TransactionStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class AdjustmentDirection(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class BaseTransactionRequest(APIModel):
    external_player_id: str = Field(
        min_length=1,
        max_length=100,
    )

    amount: PositiveAmount

    currency: CurrencyCode

    game_external_id: str | None = Field(
        default=None,
        max_length=100,
    )

    provider_reference: str | None = Field(
        default=None,
        max_length=150,
    )


class DebitRequest(BaseTransactionRequest):
    pass


class CreditRequest(BaseTransactionRequest):
    pass


class RefundRequest(BaseTransactionRequest):
    original_transaction_uuid: UUID


class RollbackRequest(APIModel):
    external_player_id: str = Field(
        min_length=1,
        max_length=100,
    )

    original_transaction_uuid: UUID

    currency: CurrencyCode

    provider_reference: str | None = Field(
        default=None,
        max_length=150,
    )


class AdjustmentRequest(APIModel):
    external_player_id: str = Field(
        min_length=1,
        max_length=100,
    )

    amount: PositiveAmount

    currency: CurrencyCode

    direction: AdjustmentDirection

    reason: str = Field(
        min_length=3,
        max_length=255,
    )


class TransactionResponse(APIModel):
    transaction_uuid: UUID
    type: TransactionType
    amount: Decimal
    currency: CurrencyCode
    status: TransactionStatus

    wallet_id: int
    provider_reference: str | None = None

    balance_before: Decimal | None = None
    balance_after: Decimal | None = None

    created_at: datetime
    updated_at: datetime


class TransactionHistoryItem(APIModel):
    transaction_uuid: UUID
    type: TransactionType
    amount: Decimal
    status: TransactionStatus
    provider_reference: str | None = None
    created_at: datetime


class TransactionHistoryResponse(APIModel):
    items: list[TransactionHistoryItem]
    total: int = Field(ge=0)