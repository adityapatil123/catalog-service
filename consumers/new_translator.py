import json
import time
from pika.exceptions import AMQPConnectionError, AMQPChannelError
from retry import retry
from config import get_config_by_name
from consumers.rabbitmq_handler import RabbitMQHandler, run_generic_consumer_new
from logger.custom_logging import log_error, log
from transformers.translation import translate_locations_into_target_language, translate_items_into_target_language
from utils.redis_utils import init_redis_cache


def process_translation(ch, method, properties, body, handler: RabbitMQHandler):
    """Process a batch of items for translation"""
    try:
        # Parse the incoming batch
        message = json.loads(body)
        batch_size = len(message.get("data", []))
        log(f"Processing batch of {batch_size} items for translation")

        # Translate based on index type
        if message["index"] == "items":
            translated_items = translate_items_into_target_language(
                message["data"],
                message["lang"]
            )
            handler.publish_batch({
                "index": "items",
                "data": translated_items
            })

        elif message["index"] == "locations":
            translated_locations = translate_locations_into_target_language(
                message["data"],
                message["lang"]
            )
            handler.publish_batch({
                "index": "locations",
                "data": translated_locations
            })

        # Acknowledge the message only after successful translation and publishing
        ch.basic_ack(delivery_tag=method.delivery_tag)
        log(f"Successfully processed and acknowledged batch of {batch_size} items")

    except Exception as e:
        log_error(f"Error processing batch: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        raise


def run_translator_consumer(queue_name: str):
    """Run the batch consumer"""
    handler = RabbitMQHandler()

    def message_handler(ch, method, properties, body):
        try:
            process_translation(ch, method, properties, body, handler)
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


@retry(exceptions=(AMQPConnectionError, AMQPChannelError),
       delay=5, jitter=(1, 3), max_delay=60)
def run_consumer():
    init_redis_cache()
    queue_name = get_config_by_name('TRANSLATOR_QUEUE_NAME')
    run_generic_consumer_new(queue_name, process_translation)


if __name__ == "__main__":
    run_consumer()
