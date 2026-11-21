"""Create a client and print its one-time API key."""

import argparse
import secrets
from datetime import datetime, timezone

from app.core.security import hash_client_api_key
from app.db.session import SessionLocal
from app.models.client import Client


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", required=True, help="Unique client code")
    parser.add_argument("--name", required=True, help="Client display name")
    args = parser.parse_args()

    api_key = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    try:
        client = Client(
            code=args.code,
            name=args.name,
            api_key_hash=hash_client_api_key(api_key),
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )
        db.add(client)
        db.commit()
        print(f"Client created: {client.code} (ID: {client.id})")
        print("Store this API key securely. It will not be displayed again:")
        print(api_key)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
