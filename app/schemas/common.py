from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
)


def normalize_currency(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Currency must be a string.")

    return value.strip().upper()


CurrencyCode = Annotated[
    str,
    BeforeValidator(normalize_currency),
    StringConstraints(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
    ),
]

PositiveAmount = Annotated[
    Decimal,
    Field(
        gt=Decimal("0"),
        max_digits=20,
        decimal_places=4,
    ),
]


class APIModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )