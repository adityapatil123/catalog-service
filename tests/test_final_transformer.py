import unittest
import json
import os
from funcy import empty

from transformers.final import transform_on_search_payload_into_final_items


class TestFinal(unittest.TestCase):

    def is_empty(self, val: dict):
        return empty(val) or len(val.keys()) == 0

    def test_on_search_simple(self):
        current_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = os.path.join(current_path, "resources/simple_on_search.json")
        with open(filepath) as f:
            json_payload = json.load(f)
            items = transform_on_search_payload_into_final_items(json_payload)

        # Verify that the document retrieval was successful
        self.assertEqual(1, len(items))

    def test_on_search_with_attributes(self):
        current_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = os.path.join(current_path, "resources/on_search_with_attributes.json")
        with open(filepath) as f:
            json_payload = json.load(f)
            items = transform_on_search_payload_into_final_items(json_payload)

        # Verify that the document retrieval was successful
        self.assertEqual(7, len(items))

    def test_on_search_with_customisation_group(self):
        current_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        filepath = os.path.join(current_path, "resources/on_search_customisation_group.json")
        with open(filepath) as f:
            json_payload = json.load(f)
            items = transform_on_search_payload_into_final_items(json_payload)

        # Verify that the document retrieval was successful
        self.assertEqual(12, len(items))
