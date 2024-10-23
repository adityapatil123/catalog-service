import json
import time
from typing import List, Dict

import pika
from bson.objectid import ObjectId
from elasticsearch.helpers import BulkIndexError
from pika.exceptions import AMQPConnectionError, AMQPChannelError
from retry import retry

from config import get_config_by_name
from consumers.rabbitmq_handler import run_generic_consumer_new, MultiQueueHandler
from logger.custom_logging import log, log_error
from services.mongo_service import update_on_search_dump_status
from transformers.full_catalog import transform_full_on_search_payload_into_default_lang_items
from transformers.incr_catalog import transform_incr_on_search_payload_into_final_items
from utils.json_utils import clean_nones
from utils.elasticsearch_utils import init_elastic_search, update_entities_with_new_provider_search_tags
from utils.mongo_utils import get_mongo_collection, collection_find_one, init_mongo_database


def process_transformation(ch, method, properties, body, handler: MultiQueueHandler):
    """Process transformation messages"""
    doc_id = None
    try:
        payload = json.loads(body)
        log(f"Processing payload: {payload}")

        doc_id = ObjectId(payload["doc_id"]) if "doc_id" in payload else None

        if doc_id:
            collection = get_mongo_collection('on_search_dump')
            on_search_payload = collection_find_one(collection, {"_id": doc_id}, keep_created_at=True)

            if not on_search_payload:
                log_error(f"On search payload not found for {doc_id}")
                update_on_search_dump_status(doc_id, "FAILED", f"On search payload not found for {doc_id}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            on_search_payload = clean_nones(on_search_payload)
            on_search_payload.pop("id", None)

            if payload["request_type"] == "full":
                update_on_search_dump_status(doc_id, "IN-PROGRESS", None)

                # Transform and publish to ES dumper
                items, offers, locations = transform_full_on_search_payload_into_default_lang_items(on_search_payload)
                handler.publish_to_es_dumper("items", items)
                handler.publish_to_es_dumper("offers", offers)
                handler.publish_to_es_dumper("locations", locations)

                # Publish to translator for each language
                for lang in get_config_by_name("LANGUAGE_LIST"):
                    if lang:
                        handler.publish_to_translator("items", items, lang)
                        handler.publish_to_translator("locations", locations, lang)

                update_on_search_dump_status(doc_id, "FINISHED")

            elif payload["request_type"] == "inc":
                update_on_search_dump_status(doc_id, "IN-PROGRESS")

                # Transform and publish incremental updates
                items, offers = transform_incr_on_search_payload_into_final_items(on_search_payload)
                handler.publish_to_es_dumper("items", items)
                handler.publish_to_es_dumper("offers", offers)

                update_on_search_dump_status(doc_id, "FINISHED")

        elif payload["request_type"] == "search-tags-update":
            # Handle search tags update
            update_entities_with_new_provider_search_tags(
                "items",
                payload["provider_id"],
                payload["provider_search_tags"]
            )
            update_entities_with_new_provider_search_tags(
                "locations",
                payload["provider_id"],
                payload["provider_search_tags"]
            )

        # Acknowledge the message after successful processing
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except BulkIndexError as e:
        log_error(f"Elasticsearch bulk index error: {e}")
        if doc_id:
            update_on_search_dump_status(doc_id, "FAILED", e.errors[0]['index']['error']['reason'])
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        log_error(f"Error processing transformation: {e}")
        if doc_id:
            update_on_search_dump_status(doc_id, "FAILED", str(e))
        ch.basic_ack(delivery_tag=method.delivery_tag)


@retry(exceptions=(AMQPConnectionError, AMQPChannelError),
       delay=5, jitter=(1, 3), max_delay=60)
def main():
    init_mongo_database()
    init_elastic_search()
    queue_name = get_config_by_name('ELASTIC_SEARCH_QUEUE_NAME')
    run_generic_consumer_new(queue_name, process_transformation)


if __name__ == "__main__":
    main()