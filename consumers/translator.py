import json
import time
from pika.exceptions import AMQPConnectionError, AMQPChannelError
from retry import retry
from config import get_config_by_name
from consumers import run_generic_consumer
from event_producer import publish_message
from logger.custom_logging import log_error, log
from transformers.translation import translate_items_into_target_language, translate_locations_into_target_language
from utils.redis_utils import init_redis_cache
from utils.rabbitmq_utils import declare_queue, consume_message, open_connection, create_channel, close_channel_and_connection


def consume_fn(message_string):
    message = json.loads(message_string)
    es_dumper_queue = get_config_by_name('ES_DUMPER_QUEUE_NAME')

    try:
        rabbitmq_connection = open_connection()
        rabbitmq_channel = create_channel(rabbitmq_connection)
        declare_queue(rabbitmq_channel, es_dumper_queue)

        if message["index"] == "items":
            translated_items = translate_items_into_target_language(message["data"], message["lang"])
            publish_message(rabbitmq_channel, es_dumper_queue, {"index": "items", "data": translated_items})
        elif message["index"] == "locations":
            translated_locations = translate_locations_into_target_language(message["data"], message["lang"])
            publish_message(rabbitmq_channel, es_dumper_queue, {"index": "locations", "data": translated_locations})
    except Exception as e:
        log_error(f"Got an exception while translating: {e}")
        raise
    finally:
        if rabbitmq_channel and rabbitmq_connection:
            close_channel_and_connection(rabbitmq_channel, rabbitmq_connection)


@retry(exceptions=(AMQPConnectionError, AMQPChannelError), delay=5, jitter=(1, 3), max_delay=60)
def run_consumer():
    init_redis_cache()
    queue_name = get_config_by_name('TRANSLATOR_QUEUE_NAME')
    run_generic_consumer(queue_name, consume_fn)


if __name__ == "__main__":
    run_consumer()
