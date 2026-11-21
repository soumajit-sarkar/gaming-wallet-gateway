from datetime import datetime

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProcessedMessage(Base):
    __tablename__ = "processed_messages"

    id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    consumer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    message_uuid: Mapped[str] = mapped_column(CHAR(36), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "consumer_name", "message_uuid", name="uq_processed_messages_consumer_message"
        ),
    )
