# pylint: disable=no-member,protected-access,redefined-outer-name
import botocore.exceptions
from django_dynamic_fixture import G

import pytest
from zinc import models, route53
from tests.fixtures import boto_client, zone  # noqa: F401
from tests.utils import hash_test_record

regions = route53.get_local_aws_regions()


@pytest.mark.django_db
def test_add_zone_record(zone):
    record = route53.Record(
        name='goo',
        type='CNAME',
        values=['google.com'],
        ttl=300,
        zone=zone.route53_zone,
    )
    zone.add_record(record)
    zone.route53_zone.commit()

    assert record.id in [r.id for r in zone.records]


@pytest.mark.django_db
def test_delete_zone_record(zone):
    record_hash = hash_test_record(zone)
    for r in zone.records:
        if r.id == record_hash:
            record = r

    zone.delete_record(record)
    zone.route53_zone.commit()

    assert record_hash not in [r.id for r in zone.records]


@pytest.mark.django_db
def test_delete_zone_record_by_hash(zone):
    record_hash = hash_test_record(zone)

    zone.delete_record_by_hash(record_hash)
    zone.route53_zone.commit()

    assert record_hash not in zone.records


@pytest.mark.django_db
def test_delete_zone_alias_record(zone):
    record = route53.Record(
        name='something',
        type='A',
        alias_target={
            'DNSName': 'test.%s' % zone.root,
            'HostedZoneId': zone.route53_zone.id,
            'EvaluateTargetHealth': False
        },
        zone=zone.route53_zone,
    )
    record_saved = zone.add_record(record)
    zone.commit()
    assert record_saved.id in [r.id for r in zone.records]

    zone.delete_record(record)
    zone.route53_zone.commit()

    assert record_saved.id not in [r.id for r in zone.records]


@pytest.mark.django_db
def test_delete_zone_alias_record_with_set_id(zone):
    record = route53.Record(
        name='_zn_something',
        type='A',
        alias_target={
            'DNSName': 'test.%s' % zone.root,
            'HostedZoneId': zone.route53_zone.id,
            'EvaluateTargetHealth': False
        },
        set_identifier='set_id',
        region=regions[0],
        zone=zone.route53_zone,
    )
    record_hash = zone.add_record(record)
    zone.route53_zone.commit()

    zone.delete_record(record)
    zone.route53_zone.commit()

    assert record_hash not in zone.records


@pytest.mark.django_db
def test_zone_delete(zone, boto_client):
    zone_id = zone.route53_zone.id
    zone_name = 'test-zinc.net.'
    # make sure we have extra records in addition to the NS and SOA
    # to ensure zone.delete handles those as well
    boto_client.change_resource_record_sets(
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
                                'Value': 'ns-1941.awszinc-50.co.uk.',
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
        boto_client.get_hosted_zone(Id=zone_id)
    assert excp.value.response['Error']['Code'] == 'NoSuchHostedZone'


def test_zone_exists_false(boto_client):
    zone_record = models.Zone(route53_id='Does/Not/Exist')
    zone = route53.Zone(zone_record)
    assert not zone.exists


@pytest.mark.django_db
def test_zone_reconcile_deleted_from_aws(zone, boto_client):
    original_id = zone.route53_id
    route53.Zone(zone)._delete_records()
    boto_client.delete_hosted_zone(Id=original_id)
    zone.route53_zone._clear_cache()
    zone.route53_zone.reconcile()
    assert zone.route53_id != original_id


@pytest.mark.django_db
def test_zone_exists_true(zone):
    assert route53.Zone(zone).exists


@pytest.mark.django_db
def test_delete_missing_zone(boto_client):
    """Test zone delete is idempotent
    If we have a zone marked deleted in the db, calling delete should be safe and
    remove the db record for good.
    """
    zone_record = G(models.Zone, route53_id='Does/Not/Exist', deleted=True)
    route53.Zone(zone_record).delete()
    assert models.Zone.objects.filter(pk=zone_record.pk).count() == 0


@pytest.mark.django_db
def test_delete_zone_no_zone_id(boto_client):
    """Test zone delete works for zones that don't have a route53_id
    """
    zone_record = G(models.Zone, route53_id=None, deleted=False)
    zone_record.soft_delete()
    assert not models.Zone.objects.filter(pk=zone_record.pk).exists()
