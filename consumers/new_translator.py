import json
import time
from pika.exceptions import AMQPConnectionError, AMQPChannelError
from retry import retry
from config import get_config_by_name
from consumers.rabbitmq_handler import MultiQueueHandler, run_generic_consumer_new
from logger.custom_logging import log_error, log
from transformers.translation import translate_locations_into_target_language, translate_items_into_target_language
from utils.redis_utils import init_redis_cache


def process_translation(ch, method, properties, body, handler: MultiQueueHandler):
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


@retry(exceptions=(AMQPConnectionError, AMQPChannelError),
       delay=5, jitter=(1, 3), max_delay=60)
def run_consumer():
    init_redis_cache()
    queue_name = get_config_by_name('TRANSLATOR_QUEUE_NAME')
    run_generic_consumer_new(queue_name, process_translation)


if __name__ == "__main__":
    run_consumer()
