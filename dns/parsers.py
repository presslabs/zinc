import json
import json_merge_patch
from rest_framework.parsers import BaseParser, JSONParser


class JSONMergePatchParser(BaseParser):
    """
    Attempt at making a parser for json merge patch payloads
    """
    media_type = 'application/merge-patch+json'

    def parse(self, stream, media_type=None, parser_context=None):
        assert 'input' in parser_context['kwargs'].keys(), (
            'Key "input" is missing from parser_context. '
            'A dictionary input must be passed to JSONMergeParser.'
        )

        input = parser_context['kwargs'].pop('input')

        try:
            json.loads(input)
        except (TypeError, ValueError):
            assert type(input) is dict, (
                "Input for JSON merge patch is neither a dict or "
                "a valid JSON string! JSONMergePatchParser isn't being "
                "used properly."
            )

        patch = JSONParser().parse(stream, media_type, parser_context)
        result = json_merge_patch.merge(input, patch)

        return result
