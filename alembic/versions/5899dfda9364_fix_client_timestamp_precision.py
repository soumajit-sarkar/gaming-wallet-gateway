"""fix client timestamp precision

Revision ID: 5899dfda9364
Revises: af2bf86d9efd
Create Date: 2026-09-04 14:22:36.199245

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = "5899dfda9364"
down_revision: Union[str, Sequence[str], None] = "af2bf86d9efd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "clients",
        "created_at",
        existing_type=mysql.DATETIME(fsp=0),
        type_=mysql.DATETIME(fsp=6),
        existing_nullable=False,
    )

    op.alter_column(
        "clients",
        "updated_at",
        existing_type=mysql.DATETIME(fsp=0),
        type_=mysql.DATETIME(fsp=6),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "clients",
        "created_at",
        existing_type=mysql.DATETIME(fsp=6),
        type_=mysql.DATETIME(fsp=0),
        existing_nullable=False,
    )

    op.alter_column(
        "clients",
        "updated_at",
        existing_type=mysql.DATETIME(fsp=6),
        type_=mysql.DATETIME(fsp=0),
        existing_nullable=False,
    )