import json

import pika


RABBITMQ_HOST = "127.0.0.1"
RABBITMQ_PORT = 5672
RABBITMQ_VHOST = "/"

RABBITMQ_USERNAME = "guest"
RABBITMQ_PASSWORD = "guest"

QUEUE_NAME = "wallet.debit.queue"


def main():
    credentials = pika.PlainCredentials(
        username=RABBITMQ_USERNAME,
        password=RABBITMQ_PASSWORD,
    )

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            virtual_host=RABBITMQ_VHOST,
            credentials=credentials,
            heartbeat=60,
        )
    )

    channel = connection.channel()

    channel.basic_qos(prefetch_count=1)

    print("Connected to RabbitMQ.")
    print(f"Waiting for messages from: {QUEUE_NAME}")

    def callback(ch, method, properties, body):
        try:
            message = json.loads(body.decode("utf-8"))

            print("\nMessage received:")
            print(json.dumps(message, indent=4))

            ch.basic_ack(
                delivery_tag=method.delivery_tag
            )

            print("\nMessage acknowledged.")

            ch.stop_consuming()

        except Exception as exc:
            print(f"Message processing failed: {exc}")

            ch.basic_nack(
                delivery_tag=method.delivery_tag,
                requeue=True,
            )

            ch.stop_consuming()

    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=callback,
        auto_ack=False,
    )

    try:
        channel.start_consuming()

    except KeyboardInterrupt:
        print("Consumer interrupted.")

    finally:
        if channel.is_open:
            channel.close()

        if connection.is_open:
            connection.close()

        print("RabbitMQ connection closed.")


if __name__ == "__main__":
    main()
