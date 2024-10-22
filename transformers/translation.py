from logger.custom_logging import log
from services import translation_service as ts
from utils.instrumentation_utils import MeasureTime
from utils.parallel_processing_utils import io_bound_parallel_computation


@MeasureTime
def translate_items_into_target_language(items, target_lang):
    log(f"Translating {len(items)} items into lang: {target_lang}")

    def translate_with_logging(x):
        try:
            return translate_an_item(x, target_lang)
        except Exception as e:
            # log(f"Got the error while translating item: {e}")
            return None  # Returning None or you can handle it differently

    # Using io_bound_parallel_computation to translate in parallel
    new_items = io_bound_parallel_computation(translate_with_logging, items)

    # Filtering out any None results due to exceptions
    final_items = [x for x in new_items if x is not None]
    log(f"Done with translation for {len(final_items)} / {len(items)} items into lang: {target_lang}")
    return final_items


@MeasureTime
def translate_locations_into_target_language(locations, target_lang):
    log(f"Translating {len(locations)} locations into lang: {target_lang}")

    def translate_with_logging(x):
        try:
            return translate_a_location(x, target_lang)
        except Exception as e:
            # log(f"Got the error while translating location: {e}")
            return None  # Returning None or you can handle it differently

    # Using io_bound_parallel_computation to translate in parallel
    new_locations = io_bound_parallel_computation(translate_with_logging, locations)

    # Filtering out any None results due to exceptions
    final_locations = [x for x in new_locations if x is not None]
    log(f"Done with translation for {len(final_locations)} / {len(locations)} locations into lang: {target_lang}")
    return final_locations


# @MeasureTime
def translate_an_item(i, target_lang):
    i["language"] = target_lang
    i["item_details"]["descriptor"] = translate_item_descriptor(i["item_details"]["descriptor"], target_lang)
    i["provider_details"]["descriptor"] = translate_item_descriptor(i["provider_details"]["descriptor"],
                                                                    target_lang)
    i["location_details"]["address"] = translate_location_address(i["location_details"].get("address", {}),
                                                                  target_lang)
    return i


# @MeasureTime
def translate_a_location(i, target_lang):
    i["language"] = target_lang
    i["provider_details"]["descriptor"] = translate_item_descriptor(i["provider_details"]["descriptor"],
                                                                    target_lang)
    i["location_details"]["address"] = translate_location_address(i["location_details"].get("address", {}),
                                                                  target_lang)
    return i


def translate_item_descriptor(item_descriptor, target_lang):
    item_descriptor["name"] = ts.get_transliterated_text(item_descriptor["name"], target_lang=target_lang)
    if "short_desc" in item_descriptor:
        item_descriptor["short_desc"] = ts.get_translated_text(item_descriptor["short_desc"], target_lang=target_lang)
    if "long_desc" in item_descriptor:
        item_descriptor["long_desc"] = ts.get_translated_text(item_descriptor["long_desc"], target_lang=target_lang)
    return item_descriptor


def translate_provider_descriptor(provider_descriptor, target_lang):
    provider_descriptor["name"] = ts.get_transliterated_text(provider_descriptor["name"], target_lang=target_lang)
    if "short_desc" in provider_descriptor:
        provider_descriptor["short_desc"] = ts.get_translated_text(provider_descriptor["short_desc"],
                                                                   target_lang=target_lang)
    if "long_desc" in provider_descriptor:
        provider_descriptor["long_desc"] = ts.get_translated_text(provider_descriptor["long_desc"],
                                                                  target_lang=target_lang)
    return provider_descriptor


def translate_location_address(location_address, target_lang):
    if "city" in location_address:
        location_address["city"] = ts.get_transliterated_text(location_address["city"], target_lang=target_lang)
    if "locality" in location_address:
        location_address["locality"] = ts.get_transliterated_text(location_address["locality"], target_lang=target_lang)
    if "state" in location_address:
        location_address["state"] = ts.get_transliterated_text(location_address["state"], target_lang=target_lang)
    if "street" in location_address:
        location_address["street"] = ts.get_transliterated_text(location_address["street"], target_lang=target_lang)
    return location_address


if __name__ == '__main__':
    item = {
        "item_details": {
            "descriptor": {
                "name": "iphone",
                "short_desc": "device",
                "long_desc": "device",
            }
        },
        "provider_details": {
            "descriptor": {
                "name": "apple",
                "short_desc": "apple",
                "long_desc": "apple",
            }
        },
        "location_details": {
            "address": {
                "city": "pune",
                "locality": "pune",
                "state": "maharashtra",
                "street": "street",
            }
        }
    }
    print(translate_an_item(item, "hi"))
