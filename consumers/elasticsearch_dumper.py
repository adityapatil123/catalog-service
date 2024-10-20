import json

from pika.exceptions import AMQPConnectionError, AMQPChannelError
from retry import retry

from config import get_config_by_name
from consumers import run_generic_consumer
from utils.elasticsearch_utils import init_elastic_search, add_documents_to_index


def consume_fn(message_string):
    message = json.loads(message_string)
    if message["index"] == "items":
        add_documents_to_index("items", message["data"])
    elif message["index"] == "offers":
        add_documents_to_index("offers", message["data"])
    elif message["index"] == "locations":
        add_documents_to_index("locations", message["data"])


@retry(exceptions=(AMQPConnectionError, AMQPChannelError), delay=5, jitter=(1, 3), max_delay=60)
def run_consumer():
    init_elastic_search()
    queue_name = get_config_by_name('ES_DUMPER_QUEUE_NAME')
    run_generic_consumer(queue_name, consume_fn)


if __name__ == "__main__":
    run_consumer()
