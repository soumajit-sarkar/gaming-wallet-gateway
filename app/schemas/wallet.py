from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.common import APIModel, CurrencyCode


class WalletCreateRequest(APIModel):
    player_id: int = Field(gt=0)
    currency: CurrencyCode


class WalletResponse(APIModel):
    id: int
    player_id: int
    currency: CurrencyCode
    balance: Decimal
    status: str
    created_at: datetime
    updated_at: datetime


class BalanceResponse(APIModel):
    wallet_id: int
    player_id: int
    currency: CurrencyCode
    balance: Decimal