"""Register or update a provider's public endpoint configuration."""

import argparse
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.provider import Provider


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()

    code = args.code.strip().upper()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    try:
        provider = db.scalar(select(Provider).where(Provider.code == code))
        if provider is None:
            provider = Provider(
                code=code,
                name=args.name,
                base_url=args.base_url.rstrip("/"),
                status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
            db.add(provider)
        else:
            provider.name = args.name
            provider.base_url = args.base_url.rstrip("/")
            provider.updated_at = now
        db.commit()
        print(f"Provider {code} saved. Configure PROVIDER_{code}_API_KEY in .env.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
