from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.provider import Provider


class ProviderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_code(self, provider_code: str) -> Provider | None:
        statement = select(Provider).where(
            Provider.code == provider_code.strip().upper()
        )
        return self.db.scalar(statement)
