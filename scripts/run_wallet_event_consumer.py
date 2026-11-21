"""Example idempotent RabbitMQ consumer for wallet transaction events.

Replace `handle_wallet_event` with the consumer's real business action. Any
side effect and the ProcessedMessage insert must share one database transaction.
"""

import json
from datetime import datetime, timezone

import pika
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.session import SessionLocal
from app.messaging.rabbitmq import QUEUE_NAME, create_connection, declare_wallet_event_topology
from app.models.processed_message import ProcessedMessage

CONSUMER_NAME = "wallet-event-audit-example"


def handle_wallet_event(payload: dict) -> None:
    # This example validates and records event receipt. It deliberately does
    # not mutate the wallet: the transaction service already committed it.
    if payload.get("event_type") != "wallet.transaction.completed":
        raise ValueError("Unsupported event type.")
    if not payload.get("transaction_uuid"):
        raise ValueError("Missing transaction_uuid.")
    print(
        "Wallet event received:",
        payload["transaction_uuid"],
        payload.get("transaction_type"),
    )


def main() -> None:
    connection = create_connection()
    channel = connection.channel()
    declare_wallet_event_topology(channel)
    channel.basic_qos(prefetch_count=10)

    def callback(ch, method, properties, body):
        try:
            payload = json.loads(body.decode("utf-8"))
            message_uuid = properties.message_id or payload.get("event_uuid")
            if not message_uuid:
                raise ValueError("Message is missing its event UUID.")

            db = SessionLocal()
            try:
                already_processed = db.scalar(
                    select(ProcessedMessage).where(
                        ProcessedMessage.consumer_name == CONSUMER_NAME,
                        ProcessedMessage.message_uuid == message_uuid,
                    )
                )
                if already_processed is None:
                    db.add(
                        ProcessedMessage(
                            consumer_name=CONSUMER_NAME,
                            message_uuid=message_uuid,
                            processed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                        )
                    )
                    # Acquire the unique inbox key before running the handler;
                    # concurrent duplicate deliveries fail here, before effects.
                    db.flush()
                    handle_wallet_event(payload)
                    db.commit()
                else:
                    db.rollback()
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except IntegrityError:
                # A concurrent delivery inserted the same inbox key first.
                db.rollback()
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            print(f"Rejecting invalid event to the dead-letter queue: {exc}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as exc:
            print(f"Event processing failed; dead-lettering for investigation: {exc}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback, auto_ack=False)
    print(f"Consuming from {QUEUE_NAME}. Press Ctrl+C to stop.")
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        pass
    finally:
        if channel.is_open:
            channel.close()
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()
