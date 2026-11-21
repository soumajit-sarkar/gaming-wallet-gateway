from datetime import datetime

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        primary_key=True,
        autoincrement=True,
    )
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    api_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ACTIVE"
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("api_key_hash", name="uq_clients_api_key_hash"),
    )
