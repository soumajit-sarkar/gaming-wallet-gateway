from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.common import APIModel, CurrencyCode


class WalletCreateRequest(APIModel):
    external_player_id: str = Field(min_length=1, max_length=100)
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