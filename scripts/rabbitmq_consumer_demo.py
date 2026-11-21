"""One-message RabbitMQ consumer smoke test (not a production worker)."""

import json
import os

import pika


def main() -> None:
    host = os.getenv("RABBITMQ_HOST", "127.0.0.1")
    port = int(os.getenv("RABBITMQ_PORT", "5672"))
    virtual_host = os.getenv("RABBITMQ_VHOST", "/")
    username = os.getenv("RABBITMQ_USERNAME", "guest")
    password = os.getenv("RABBITMQ_PASSWORD", "guest")
    queue_name = os.getenv("RABBITMQ_QUEUE", "wallet.debit.queue")

    credentials = pika.PlainCredentials(username=username, password=password)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=host,
            port=port,
            virtual_host=virtual_host,
            credentials=credentials,
            heartbeat=60,
        )
    )
    channel = connection.channel()
    channel.basic_qos(prefetch_count=1)

    print(f"Connected. Waiting for one message from {queue_name!r}.")

    def callback(ch, method, properties, body):
        try:
            message = json.loads(body.decode("utf-8"))
            print(json.dumps(message, indent=2))
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"Invalid JSON message; rejecting without requeue: {exc}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        finally:
            ch.stop_consuming()

    channel.basic_consume(
        queue=queue_name,
        on_message_callback=callback,
        auto_ack=False,
    )
    try:
        channel.start_consuming()
    finally:
        if channel.is_open:
            channel.close()
        if connection.is_open:
            connection.close()
        print("RabbitMQ connection closed.")


if __name__ == "__main__":
    main()
