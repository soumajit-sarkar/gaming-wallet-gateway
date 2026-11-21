"""Continuously publish committed outbox events to RabbitMQ."""

import time

from app.db.session import SessionLocal
from app.messaging.outbox_publisher import OutboxPublisher
from app.messaging.rabbitmq import (
    create_connection,
    declare_wallet_event_topology,
    publish_wallet_event,
)


def main() -> None:
    connection = create_connection()
    channel = connection.channel()
    declare_wallet_event_topology(channel)
    channel.confirm_delivery()

    publisher = OutboxPublisher(
        SessionLocal,
        lambda event: publish_wallet_event(channel, event),
        batch_size=50,
        lease_seconds=60,
        max_backoff_seconds=300,
        max_attempts=8,
    )
    print("Outbox publisher started. Press Ctrl+C to stop.")
    try:
        while True:
            published_or_claimed = publisher.run_once()
            if published_or_claimed == 0:
                time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping outbox publisher.")
    finally:
        if channel.is_open:
            channel.close()
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()
