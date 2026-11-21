from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_client_api_key
from app.db.session import get_db
from app.models.client import Client


DbSession = Annotated[Session, Depends(get_db)]


def get_current_client(
    db: DbSession,
    x_client_api_key: Annotated[str | None, Header(alias="X-Client-API-Key")] = None,
) -> Client:
    if not x_client_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing client API key.",
        )

    key_hash = hash_client_api_key(x_client_api_key)
    client = db.scalar(
        select(Client).where(
            Client.api_key_hash == key_hash,
            Client.status == "ACTIVE",
        )
    )
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client API key.",
        )
    return client


CurrentClient = Annotated[Client, Depends(get_current_client)]
