"""Register a provider game in the local catalog."""

import argparse
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.game import Game
from app.models.provider import Provider


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider-code", required=True)
    parser.add_argument("--external-id", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    try:
        provider = db.scalar(
            select(Provider).where(Provider.code == args.provider_code.strip().upper())
        )
        if provider is None:
            raise SystemExit("Provider does not exist. Register it first.")
        game = db.scalar(
            select(Game).where(
                Game.provider_id == provider.id,
                Game.external_id == args.external_id,
            )
        )
        if game is None:
            game = Game(
                provider_id=provider.id,
                external_id=args.external_id,
                name=args.name,
                status="ACTIVE",
                created_at=now,
                updated_at=now,
            )
            db.add(game)
        else:
            game.name = args.name
            game.updated_at = now
        db.commit()
        print(f"Game {args.external_id} registered under {provider.code}.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
