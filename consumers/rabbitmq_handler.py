import json
import time
from typing import Dict
import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError, StreamLostError
from retry import retry
from config import get_config_by_name
from logger.custom_logging import log_error, log


class RabbitMQHandler:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.es_dumper_queue = get_config_by_name('ES_DUMPER_QUEUE_NAME')
        self._connect()

    def _connect(self):
        """Establish connection with RabbitMQ"""
        rabbitmq_host = get_config_by_name('RABBITMQ_HOST')
        rabbitmq_creds = get_config_by_name('RABBITMQ_CREDS')

        params = {
            'host': rabbitmq_host,
            'heartbeat': 600,
            'blocked_connection_timeout': 300,
            'connection_attempts': 3,
            'retry_delay': 5
        }

        if rabbitmq_creds:
            credentials = pika.PlainCredentials(
                get_config_by_name('RABBITMQ_USERNAME'),
                get_config_by_name('RABBITMQ_PASSWORD')
            )
            params['credentials'] = credentials

        self.connection = pika.BlockingConnection(pika.ConnectionParameters(**params))
        self.channel = self.connection.channel()
        self.channel.basic_qos(prefetch_count=get_config_by_name('CONSUMER_MAX_WORKERS', 10))
        self.channel.confirm_delivery()  # Enable publisher confirms

        # Declare the ES dumper queue
        self.channel.queue_declare(queue=self.es_dumper_queue)

    def ensure_connection(self):
        """Ensure connection is alive, reconnect if needed"""
        try:
            if not self.connection or not self.connection.is_open:
                self._connect()
            elif not self.channel or not self.channel.is_open:
                self.channel = self.connection.channel()
                self.channel.basic_qos(prefetch_count=get_config_by_name('CONSUMER_MAX_WORKERS', 10))
                self.channel.confirm_delivery()
                self.channel.queue_declare(queue=self.es_dumper_queue)
        except Exception as e:
            log_error(f"Connection error: {e}")
            self._connect()

    @retry(exceptions=(AMQPConnectionError, AMQPChannelError, StreamLostError),
           tries=3, delay=2, backoff=2)
    def publish_batch(self, message: Dict):
        """Publish translated batch with retry logic"""
        self.ensure_connection()

        try:
            message_body = json.dumps(message)

            self.channel.basic_publish(
                exchange='',
                routing_key=self.es_dumper_queue,
                body=message_body,
                properties=pika.BasicProperties(
                    # delivery_mode=2,  # Make message persistent
                    content_type='application/json'
                ),
                mandatory=True
            )

            log(f"Successfully published batch to {self.es_dumper_queue}")

        except Exception as e:
            log_error(f"Error publishing batch: {e}")
            raise

    def close(self):
        """Close connection and channel"""
        if self.channel and self.channel.is_open:
            try:
                self.channel.close()
            except:
                pass
        if self.connection and self.connection.is_open:
            try:
                self.connection.close()
            except:
                pass



def run_generic_consumer_new(queue_name: str, process_fn):
    """Run the batch consumer"""
    handler = RabbitMQHandler()

    def message_handler(ch, method, properties, body):
        try:
            process_fn(ch, method, properties, body, handler)
        except Exception as e:
            log_error(f"Batch processing error: {e}")

    while True:
        try:
            handler.ensure_connection()

            # Declare input queue
            handler.channel.queue_declare(queue=queue_name)

            # Set up consumer
            handler.channel.basic_consume(
                queue=queue_name,
                on_message_callback=message_handler,
                auto_ack=False
            )

            log(f"Starting to consume batches from queue: {queue_name}")
            handler.channel.start_consuming()

        except (AMQPConnectionError, AMQPChannelError) as e:
            log_error(f"RabbitMQ connection error: {e}")
            time.sleep(5)

        except Exception as e:
            log_error(f"Unexpected error: {e}")
            time.sleep(5)

        finally:
            try:
                handler.channel.stop_consuming()
            except:
                pass

            try:
                handler.close()
            except:
                pass