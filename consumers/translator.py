import json

from pika.exceptions import AMQPConnectionError
from retry import retry

from config import get_config_by_name
from event_producer import publish_message
from logger.custom_logging import log_error
from transformers.translation import translate_items_into_target_language, translate_locations_into_target_language
from utils.redis_utils import init_redis_cache
from utils.rabbitmq_utils import declare_queue, consume_message, open_connection_and_channel_if_not_already_open, \
    open_connection, create_channel, close_channel_and_connection
from utils.transliteration_model_utils import create_language_models


def consume_fn(message_string):
    message = json.loads(message_string)
    es_dumper_queue = get_config_by_name('ES_DUMPER_QUEUE_NAME')
    rabbitmq_connection = open_connection()
    rabbitmq_channel = create_channel(rabbitmq_connection)
    declare_queue(rabbitmq_channel, es_dumper_queue)

    try:
        if message["index"] == "items":
            translated_items = translate_items_into_target_language(message["data"], message["lang"])
            publish_message(rabbitmq_channel, es_dumper_queue, {"index": "items", "data": translated_items})
        elif message["index"] == "locations":
            translated_locations = translate_locations_into_target_language(message["data"], message["lang"])
            publish_message(rabbitmq_channel, es_dumper_queue, {"index": "locations", "data": translated_locations})
    except Exception as e:
        log_error(f"Got an exception while translating {e}")
    finally:
        close_channel_and_connection(rabbitmq_channel, rabbitmq_connection)


@retry(AMQPConnectionError, delay=5, jitter=(1, 3))
def run_consumer():
    init_redis_cache()
    queue_name = get_config_by_name('TRANSLATOR_QUEUE_NAME')
    connection, channel = open_connection_and_channel_if_not_already_open()
    declare_queue(channel, queue_name)
    create_language_models()
    consume_message(connection, channel, queue_name=queue_name, consume_fn=consume_fn)


if __name__ == "__main__":
    run_consumer()
