import json
import json_merge_patch
from rest_framework.parsers import BaseParser, JSONParser

from dns.utils.generic import dict_key_intersection


class JSONMergePatchParser(BaseParser):
    """
    Attempt at making a parser for json merge patch payloads
    """
    media_type = 'application/merge-patch+json'

    def parse(self, stream, media_type=None, parser_context=None):
        zone = parser_context['view'].get_object()
        zone_records = zone.records
        patch = JSONParser().parse(stream, media_type, parser_context)

        for key, record in patch['records'].items():
            if not record and key in zone_records:
                patch['records'].update({key: {'delete': True}})

        zone_records = dict_key_intersection(zone_records, patch['records'])

        return json_merge_patch.merge({'records': zone_records}, patch)
