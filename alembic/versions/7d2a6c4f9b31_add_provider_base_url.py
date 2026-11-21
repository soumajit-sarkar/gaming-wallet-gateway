"""add provider base URL configuration

Revision ID: 7d2a6c4f9b31
Revises: 5a7d2c9e4b61
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7d2a6c4f9b31"
down_revision: Union[str, Sequence[str], None] = "5a7d2c9e4b61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("providers", sa.Column("base_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("providers", "base_url")
