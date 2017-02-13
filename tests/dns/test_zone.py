# pylint: disable=no-member,protected-access,redefined-outer-name
import pytest
from django_dynamic_fixture import G

from tests.fixtures import boto_client, zone
from dns import models as m
from zinc.vendors import hashids
from tests.utils import strip_ns_and_soa


@pytest.mark.django_db
def test_add_zone_record(zone):
    zone, _ = zone

    record = {
        'name': 'goo',
        'type': 'CNAME',
        'values': ['google.com'],
        'ttl': 300,
    }
    zone.add_record(record)
    zone.save()

    print(zone.records)
    assert 'D7ldejBgkXJwR' in zone.records


@pytest.mark.django_db
def test_delete_zone_record(zone):
    zone, _ = zone
    record_hash = 'GW5Xxvn9kYvmd'
    record = zone.records[record_hash]

    zone.delete_record(record)
    zone.save()

    assert record_hash not in zone.records


@pytest.mark.django_db
def test_delete_zone_record_by_hash(zone):
    zone, _ = zone
    record_hash = 'GW5Xxvn9kYvmd'

    zone.delete_record_by_hash(record_hash)
    zone.save()

    assert record_hash not in zone.records


