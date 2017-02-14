# pylint: disable=no-member,protected-access,redefined-outer-name
import botocore.exceptions
import pytest
from django_dynamic_fixture import G

from dns import models as m
from dns.utils.route53 import get_local_aws_regions
from tests.fixtures import boto_client, zone  # pylint: disable=unused-import

regions = get_local_aws_regions()


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


@pytest.mark.django_db
def test_delete_zone_alias_record(zone):
    zone, _ = zone
    record = {
        'name': '_zn_something',
        'type': 'A',
        'AliasTarget': {
            'DNSName': 'test',
            'HostedZoneId': zone.route53_zone.id,
            'EvaluateTargetHealth': False
        },
    }
    record_hash = zone.add_record(record)

    zone.delete_record(record)
    zone.save()

    assert record_hash not in zone.records


@pytest.mark.django_db
def test_delete_zone_alias_record_with_set_id(zone):
    zone, _ = zone
    record = {
        'name': '_zn_something',
        'type': 'A',
        'AliasTarget': {
            'DNSName': 'test',
            'HostedZoneId': zone.route53_zone.id,
            'EvaluateTargetHealth': False
        },
        'SetIdentifier': 'set_id',
        'Region': regions[0]
    }
    record_hash = zone.add_record(record)

    zone.delete_record(record)
    zone.save()

    assert record_hash not in zone.records


@pytest.mark.django_db
def test_zone_delete(zone):
    zone, client = zone
    zone_id = zone.route53_zone.id
    zone_name = 'test-zinc.net.'
    client.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            'Comment': 'zinc-fixture',
            'Changes': [
                {
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'Name': 'some_ns.%s' % zone_name,
                        'Type': 'NS',
                        'TTL': 300,
                        'ResourceRecords': [
                            {
                                'Value': 'ns-1941.awsdns-50.co.uk.',
                            }
                        ]
                    }
                },
                {
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'Name': 'some_a.%s' % zone_name,
                        'Type': 'A',
                        'TTL': 300,
                        'ResourceRecords': [
                            {
                                'Value': '1.1.1.2',
                            }
                        ]
                    }
                }
            ]
        }
    )
    zone.route53_zone.delete()
    with pytest.raises(botocore.exceptions.ClientError) as excp:
        client.get_hosted_zone(Id=zone_id)
    assert excp.value.response['Error']['Code'] == 'NoSuchHostedZone'
