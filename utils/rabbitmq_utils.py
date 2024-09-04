import functools
import threading
import concurrent.futures
import pika
from config import get_config_by_name
from logger.custom_logging import log, log_error

# Set a timeout in seconds (e.g., 30 minutes)
TIMEOUT = 1800  # 1800 seconds = 30 minutes

def open_connection_and_channel_if_not_already_open(old_connection, old_channel):
    if old_connection and old_connection.is_open:
        log("Getting old connection and channel")
        return old_connection, old_channel
    else:
        log("Getting new connection and channel")
        rabbitmq_host = get_config_by_name('RABBITMQ_HOST')
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
        channel = connection.channel()
        return connection, channel

def open_connection():
    rabbitmq_host = get_config_by_name('RABBITMQ_HOST')
    rabbitmq_creds = get_config_by_name('RABBITMQ_CREDS')
    if rabbitmq_creds:
        credentials = pika.PlainCredentials(get_config_by_name('RABBITMQ_USERNAME'),
                                            get_config_by_name('RABBITMQ_PASSWORD'))
        return pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host, credentials=credentials))
    else:
        return pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))

def close_connection(connection):
    connection.close()

def create_channel(connection):
    channel = connection.channel()
    channel.basic_qos(prefetch_count=get_config_by_name('CONSUMER_MAX_WORKERS', 10))
    return channel

def declare_queue(channel, queue_name):
    channel.queue_declare(queue=queue_name)

def publish_message_to_queue(channel, exchange, routing_key, body, properties=None):
    log(f"Publishing message of {body}")
    channel.basic_publish(exchange=exchange, routing_key=routing_key, body=body, properties=properties)

def acknowledge_message(ch, delivery_tag, body, success=True):
    try:
        ch.basic_ack(delivery_tag)
        log(f"Acked message {body} successfully!" if success else f"Acked message {body} due to timeout!")
    except Exception as e:
        log_error(f"Failed to ack message {body}: {e}")

def consume_message(connection, channel, queue_name, consume_fn):
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=get_config_by_name('CONSUMER_MAX_WORKERS', 10))

    def do_work(ch, delivery_tag, body):
        thread_id = threading.get_ident()
        log(f'Thread id: {thread_id} Delivery tag: {delivery_tag} Message body: {body}')

        try:
            consume_fn(body)
            success = True
        except Exception as e:
            log_error(f"Error processing message {body}: {e}")
            success = False

        if connection and connection.is_open:
            connection.add_callback_threadsafe(functools.partial(acknowledge_message, ch, delivery_tag, body, success))
        else:
            log_error("Connection is closed. Cannot add callback.")

    def on_message(ch, method_frame, header_frame, body):
        delivery_tag = method_frame.delivery_tag
        if len(ch.consumer_tags) == 0:
            log_error("Nobody is listening. Stopping the consumer!")
            return

        # Use ThreadPoolExecutor to handle the message processing with a timeout
        future = executor.submit(do_work, ch, delivery_tag, body)

        try:
            # Wait for the task to complete within the timeout period
            future.result(timeout=TIMEOUT)
        except concurrent.futures.TimeoutError:
            log_error(f"Timeout occurred for message {body}, acking the message and moving on")
            future.cancel()
            acknowledge_message(ch, delivery_tag, body, success=False)

    channel.basic_consume(queue=queue_name, on_message_callback=on_message, auto_ack=False)
    log('Waiting for messages:')

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    finally:
        executor.shutdown(wait=True)
        connection.close()
