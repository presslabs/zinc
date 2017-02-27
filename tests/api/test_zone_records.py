# pylint: disable=no-member,unused-argument,protected-access,redefined-outer-name
import pytest
import json

from django_dynamic_fixture import G
from django.core.exceptions import ObjectDoesNotExist

from tests.fixtures import api_client, boto_client, zone
from tests.utils import (strip_ns_and_soa, hash_test_record, aws_strip_ns_and_soa, aws_sort_key,
                         get_test_record, record_to_aws, hash_record)
from dns import models as m
from zinc.vendors.hashids import encode_record


@pytest.mark.django_db
def test_get_record(api_client, zone):
    zone, client = zone
    G(m.Zone)

    response = api_client.get(
        '/zones/{}/records/{}'.format(zone.id, hash_test_record(zone))
    )

    assert response.data == get_test_record(zone)


@pytest.mark.django_db
def test_create_record(api_client, zone):
    zone, client = zone
    G(m.Zone)

    record = {
        'name': 'record1',
        'type': 'A',
        'ttl': 300,
        'values': ['1.2.3.4']
    }
    record_hash = encode_record(record, zone.route53_zone.id)
    response = api_client.post(
        '/zones/{}/records'.format(zone.id),
        data=record
    )

    assert response.data == {
        **record,
        'id': record_hash,
        'dirty': False,
        'managed': False,
        'url': 'http://testserver/zones/%s/records/%s' % (zone.id, record_hash)
    }
    assert aws_strip_ns_and_soa(
        client.list_resource_record_sets(HostedZoneId=zone.route53_zone.id), zone.root
    ) == sorted([
        record_to_aws(record, zone.root),
        record_to_aws(get_test_record(zone), zone.root)
    ], key=aws_sort_key)


@pytest.mark.django_db
def test_update_record_values(api_client, zone):
    zone, client = zone
    G(m.Zone)

    record = {
        'values': ['1.2.3.4']
    }
    response = api_client.patch(
        '/zones/{}/records/{}'.format(zone.id, hash_test_record(zone)),
        data=record
    )

    assert response.data == {
        **get_test_record(zone),
        **record
    }
    assert aws_strip_ns_and_soa(
        client.list_resource_record_sets(HostedZoneId=zone.route53_zone.id), zone.root
    ) == sorted([
        record_to_aws({
            **get_test_record(zone),
            **record
        }, zone.root)
    ], key=aws_sort_key)


@pytest.mark.django_db
def test_update_record_ttl(api_client, zone):
    zone, client = zone
    G(m.Zone)

    record = {
        'ttl': 580
    }
    response = api_client.patch(
        '/zones/{}/records/{}'.format(zone.id, hash_test_record(zone)),
        data=record
    )

    assert response.data == {
        **get_test_record(zone),
        **record
    }
    assert aws_strip_ns_and_soa(
        client.list_resource_record_sets(HostedZoneId=zone.route53_zone.id), zone.root
    ) == sorted([
        record_to_aws({
            **get_test_record(zone),
            **record
        }, zone.root)
    ], key=aws_sort_key)


@pytest.mark.django_db
def test_update_record_type(api_client, zone):
    zone, _ = zone
    G(m.Zone)

    record = {
        'type': 'CNAME'
    }
    response = api_client.patch(
        '/zones/{}/records/{}'.format(zone.id, hash_test_record(zone)),
        data=record
    )
    assert response.data == {
        'non_field_errors': ["Can't update 'name' and 'type' fields. "]
    }


@pytest.mark.django_db
def test_update_record_name(api_client, zone):
    zone, _ = zone
    G(m.Zone)

    record = {
        'name': 'CNAME'
    }
    response = api_client.patch(
        '/zones/{}/records/{}'.format(zone.id, hash_test_record(zone)),
        data=record
    )
    assert response.data == {
        'non_field_errors': ["Can't update 'name' and 'type' fields. "]
    }


@pytest.mark.django_db
def test_record_deletion(api_client, zone):
    zone, client = zone
    record_hash = hash_test_record(zone)
    response = api_client.delete(
        '/zones/%s/records/%s' % (zone.id, record_hash),
    )
    # assert response.code == 204
    assert strip_ns_and_soa(zone.records) == []
    assert aws_strip_ns_and_soa(
        client.list_resource_record_sets(HostedZoneId=zone.route53_zone.id),
        zone.root
    ) == []


@pytest.mark.django_db
def test_delete_nonexistent_records(api_client, zone):
    zone, _ = zone
    record2 = {
        'name': 'detest',
        'ttl': 400,
        'type': 'NS',
        'values': ['ns.test.com', 'ns2.test.com']
    }
    zone.records = [record2]
    zone.save()
    response = api_client.delete(
        '/zones/%s/records/%s' % (zone.id, 'asldmpoqfqee')
    )
    # assert response.status_code == 204
    assert response.data == {'detail': 'Record not found.'}


@pytest.mark.django_db
def test_patch_nonexistent_records(api_client, zone):
    zone, _ = zone
    response = api_client.patch(
        '/zones/%s/records/%s' % (zone.id, 'asldmpoqfqee')
    )
    # assert response.status_code == 204
    assert response.data == {'detail': 'Record not found.'}


@pytest.mark.django_db
def test_add_record_without_values(api_client, zone):
    zone, _ = zone
    record = {
        'name': 'test',
        'ttl': 400,
        'type': 'A',
    }
    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data=record
    )
    assert response.data == {'values': ['This field is required.']}


@pytest.mark.django_db
def test_add_record_without_ttl(api_client, zone):
    zone, _ = zone
    record = {
        'name': 'test',
        'type': 'A',
        'valuse': ['4.5.6.7']
    }
    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data=record
    )
    assert response.data == {
        'ttl': ['This field is required. If record type is not POLICY_RECORD.']
    }


@pytest.mark.django_db
def test_add_record_invalid_ttl(api_client, zone):
    zone, _ = zone
    record = {
        'name': 'test',
        'type': 'A',
        'ttl': 23,
        'valuse': ['4.5.6.7'],
    }
    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data=record
    )
    assert response.data == {
        'ttl': ['Ensure this value is greater than or equal to 300.']
    }


@pytest.mark.django_db
def test_hidden_records(api_client, zone):
    zone, _ = zone
    zone.add_record({
        'name': '{}_ceva'.format(m.RECORD_PREFIX),
        'ttl': 300,
        'type': 'A',
        'values': ['1.2.3.4']
    })
    zone.save()
    response = api_client.get(
        '/zones/%s' % zone.id,
    )
    assert strip_ns_and_soa(response.data['records']) == [
        get_test_record(zone)
    ]


@pytest.mark.django_db
def test_alias_records(api_client, zone):
    zone, _ = zone
    alias_record = {
        'name': 'ceva',
        'type': 'A',
        'AliasTarget': {
            'HostedZoneId': zone.route53_zone.id,
            'DNSName': 'test',
            'EvaluateTargetHealth': False
        },
    }
    zone.add_record(alias_record)
    zone.save()
    response = api_client.get(
        '/zones/%s' % zone.id,
    )

    def sort_key(record):
        return record['name']

    assert sorted(strip_ns_and_soa(response.data['records']), key=sort_key) == sorted([
        get_test_record(zone),
        {
            'id': hash_record(alias_record, zone),
            'url': 'http://testserver/zones/{}/records/{}'.format(
                zone.id,
                hash_record(alias_record, zone)),
            'name': 'ceva',
            'type': 'A',
            'dirty': False,
            'managed': True,
            'values': ['ALIAS test.test-zinc.net.']
        }
    ], key=sort_key)


@pytest.mark.django_db
def test_validation_prefix(api_client, zone):
    zone, _ = zone
    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data={
            'name': '_zn_something',
            'ttl': 300,
            'type': 'CNAME',
            'values': ['www.google.com']
        }
    )

    assert response.data == {
        'name': ['Record _zn_something can\'t start with _zn. It\'s a reserved prefix.']
    }
