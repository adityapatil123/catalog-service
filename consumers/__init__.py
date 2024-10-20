import time
from pika.exceptions import AMQPConnectionError, AMQPChannelError
from logger.custom_logging import log_error, log
from utils.rabbitmq_utils import declare_queue, consume_message, open_connection, create_channel, close_channel_and_connection


def run_generic_consumer(queue_name, consume_fn):
    while True:
        try:
            connection = open_connection()
            channel = create_channel(connection)

            # Enable heartbeats
            connection.add_on_connection_blocked_callback(on_connection_blocked)
            connection.add_on_connection_unblocked_callback(on_connection_unblocked)

            declare_queue(channel, queue_name)

            log("Starting to consume messages...")
            consume_message(connection, channel, queue_name=queue_name, consume_fn=consume_fn)
        except (AMQPConnectionError, AMQPChannelError) as e:
            log_error(f"RabbitMQ connection error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            log_error(f"Unexpected error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        finally:
            if channel and connection:
                close_channel_and_connection(channel, connection)


def on_connection_blocked(connection, method_frame):
    log_error(f"Connection blocked. Reason: {method_frame.reason}")


def on_connection_unblocked(connection, method_frame):
    log("Connection unblocked")
