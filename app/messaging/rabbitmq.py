import json
from typing import Any

import pika

from app.core.config import settings

EXCHANGE_NAME = "wallet.events"
QUEUE_NAME = "wallet.events.queue"
ROUTING_KEY = "wallet.transaction.completed"
DEAD_LETTER_EXCHANGE = "wallet.events.dlx"
DEAD_LETTER_QUEUE = "wallet.events.dead.queue"
DEAD_LETTER_ROUTING_KEY = "wallet.events.dead"


def create_connection() -> pika.BlockingConnection:
    credentials = pika.PlainCredentials(
        settings.rabbitmq_username,
        settings.rabbitmq_password,
    )
    parameters = pika.ConnectionParameters(
        host=settings.rabbitmq_host,
        port=settings.rabbitmq_port,
        virtual_host=settings.rabbitmq_vhost,
        credentials=credentials,
        heartbeat=60,
        blocked_connection_timeout=30,
        connection_attempts=3,
        retry_delay=2,
    )
    return pika.BlockingConnection(parameters)


def declare_wallet_event_topology(channel: Any) -> None:
    channel.exchange_declare(
        exchange=EXCHANGE_NAME,
        exchange_type="topic",
        durable=True,
    )
    channel.exchange_declare(
        exchange=DEAD_LETTER_EXCHANGE,
        exchange_type="direct",
        durable=True,
    )
    channel.queue_declare(queue=DEAD_LETTER_QUEUE, durable=True)
    channel.queue_bind(
        queue=DEAD_LETTER_QUEUE,
        exchange=DEAD_LETTER_EXCHANGE,
        routing_key=DEAD_LETTER_ROUTING_KEY,
    )
    channel.queue_declare(
        queue=QUEUE_NAME,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
            "x-dead-letter-routing-key": DEAD_LETTER_ROUTING_KEY,
        },
    )
    channel.queue_bind(
        queue=QUEUE_NAME,
        exchange=EXCHANGE_NAME,
        routing_key=ROUTING_KEY,
    )


def publish_wallet_event(channel: Any, event: dict[str, Any]) -> None:
    body = json.dumps(event["payload"], separators=(",", ":")).encode("utf-8")
    confirmed = channel.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key=event["event_type"],
        body=body,
        properties=pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,
            message_id=event["event_uuid"],
            type=event["event_type"],
        ),
        mandatory=True,
    )
    if confirmed is False:
        raise RuntimeError("RabbitMQ did not confirm the published event.")
