# pylint: disable=no-member,unused-argument,protected-access,redefined-outer-name
import pytest
import json

from django_dynamic_fixture import G
from django.core.exceptions import ObjectDoesNotExist

from tests.fixtures import api_client, boto_client, zone
from dns import models as m


def strip_ns_and_soa(records):
    """The NS and SOA records are managed by AWS, so we won't care about them in tests"""
    return {
        record_id: record
        for record_id, record in records.items()
        if record['name'] != '@' and record['type'] not in ('NS', 'SOA')
    }


@pytest.mark.django_db
def test_create_zone(api_client, boto_client):
    root = 'example.com.presslabs.com.'
    resp = api_client.post(
        '/zones/',
        data={
            'root': root,
        }
    )
    assert resp.status_code == 201, resp.data
    assert resp.data['root'] == root
    _id = resp.data['id']
    assert list(m.Zone.objects.all().values_list('id', 'root')) == [(_id, root)]


@pytest.mark.django_db
def test_create_zone_passing_wrong_params(api_client, boto_client):
    resp = api_client.post(
        '/zones/',
        data={
            'id': 'asd',
            'root': 'asdasd'
        }
    )
    assert resp.status_code == 400, resp.data
    assert resp.data['root'] == ['Invalid root domain']


@pytest.mark.django_db
def test_list_zones(api_client, boto_client):
    zones = [G(m.Zone, root='1.test-zinc.com.', route53_id=None),
             G(m.Zone, root='2.test-zinc.com.', route53_id=None)]

    response = api_client.get('/zones/')

    assert [result['url'] for result in response.data['results']] == [
        "http://testserver/zones/{}".format(zone.id) for zone in zones]
    assert (list(m.Zone.objects.all().values_list('id', 'root')) ==
            [(zone['id'], zone['root']) for zone in response.data['results']])


@pytest.mark.django_db
def test_detail_zone(api_client, zone):
    zone, client = zone
    response = api_client.get(
        '/zones/%s/' % zone.id,
    )
    assert strip_ns_and_soa(response.data['records']) == {
        '7Q45ew5E0vOMq': {
            'values': ['1.1.1.1'],
            'name': 'test',
            'ttl': 300,
            'type': 'A',
        }
    }


@pytest.mark.django_db
def test_zone_patch_with_records(api_client, zone):
    zone, client = zone
    record_hash = '7Q45ew5E0vOMq'
    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                record_hash: {
                    'values': ['2.2.2.2'],
                    'type': 'A',
                    'ttl': 300,
                    'name': 'test'
                }
            }
        }),
        content_type='application/merge-patch+json'
    )
    assert response.data['records'][record_hash] == {
        'ttl': 300,
        'type': 'A',
        'name': 'test',
        'values': ['2.2.2.2']
    }


@pytest.mark.django_db
def test_update_bunch_of_records(api_client, zone):
    zone, client = zone
    record1_hash = '7Q45ew5E0vOMq'
    record1 = {
        'values': ['2.2.2.2'],
        'type': 'A',
        'ttl': 300,
        'name': 'test'
    }
    record2 = {
        'name': 'detest',
        'ttl': 400,
        'type': 'NS',
        'values': ['ns.test.com', 'ns2.test.com']
    }
    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                record1_hash: record1,
                'new': record2
            }
        }),
        content_type='application/merge-patch+json'
    )
    assert response.data['records'][record1_hash] == record1
    assert response.data['records']['50Y6bP8D1V4B3'] == record2


@pytest.mark.django_db
def test_delete_bunch_of_records(api_client, zone):
    zone, client = zone
    record1_hash = '7Q45ew5E0vOMq'
    record1 = {
        'values': ['2.2.2.2'],
        'type': 'A',
        'ttl': 300,
        'name': 'test'
    }
    record2_hash = '50Y6bP8D1V4B3'
    record2 = {
        'name': 'detest',
        'ttl': 400,
        'type': 'NS',
        'values': ['ns.test.com', 'ns2.test.com']
    }
    record3_hash = 'ELGbwLwmXjwWm'
    record3 = {
        'name': 'cdn',
        'ttl': 400,
        'type': 'A',
        'values': ['1.2.3.4', '2.3.4.5']
    }
    zone.records = {'new': record2, '234': record3}
    zone.save()
    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                record1_hash: record1,
                record2_hash: None,
                record3_hash: None
            }
        }),
        content_type='application/merge-patch+json'
    )
    assert response.data['records'][record1_hash] == record1
    assert record2_hash not in response.data['records']
    assert record3_hash not in response.data['records']


@pytest.mark.django_db
def test_delete_nonexistent_records(api_client, zone):
    zone, client = zone
    record1_hash = '7Q45ew5E0vOMq'
    record1 = {
        'values': ['2.2.2.2'],
        'type': 'A',
        'ttl': 300,
        'name': 'test'
    }
    record2_hash = '50Y6bP8D1V4B3'
    record2 = {
        'name': 'detest',
        'ttl': 400,
        'type': 'NS',
        'values': ['ns.test.com', 'ns2.test.com']
    }
    record3_hash = 'non-existen'
    zone.records = {'new': record2}
    zone.save()
    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                record1_hash: record1,
                record2_hash: None,
                record3_hash: None
            }
        }),
        content_type='application/merge-patch+json'
    )
    assert response.data['records'][record1_hash] == record1
    assert record2_hash not in response.data['records']
    assert record3_hash not in response.data['records']


@pytest.mark.django_db
def test_zone_delete_record(api_client, zone):
    zone, client = zone
    record_hash = '7Q45ew5E0vOMq'
    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                record_hash: None
            }
        }),
        content_type='application/merge-patch+json'
    )
    assert record_hash not in response.data['records']


@pytest.mark.django_db
def test_delete_a_zone(api_client, zone, settings):
    zone, client = zone
    settings.CELERY_ALWAYS_EAGER = True
    response = api_client.delete(
        '/zones/%s/' % zone.id
    )

    with pytest.raises(ObjectDoesNotExist) as _:
        m.Zone.objects.get(pk=zone.id)

    assert not response.data


@pytest.mark.django_db
def test_add_record_without_values(api_client, zone):
    zone, client = zone
    record2_hash = 'new'
    record2 = {
        'name': 'test',
        'ttl': 400,
        'type': 'A',
    }
    response = api_client.post(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                record2_hash: record2
            }
        }),
        content_type='application/merge-patch+json'
    )
    assert response.data['records'] == {'values': ['This field is required.']}


@pytest.mark.django_db
def test_add_record_without_ttl(api_client, zone):
    zone, client = zone
    record2_hash = 'new'
    record2 = {
        'name': 'something',
        'type': 'A',
        'values': ['1.2.3.4'],
    }
    response = api_client.post(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                record2_hash: record2
            }
        }),
        content_type='application/merge-patch+json'
    )
    assert response.data['records'] == {
        'non_field_errors': ["Field 'ttl' is required. If record type is not POLICY_REOCRD."]
    }


@pytest.mark.django_db
def test_add_record_ttl_invalid(api_client, zone):
    zone, client = zone
    record2_hash = 'new'
    record2 = {
        'name': 'something',
        'type': 'A',
        'values': ['1.2.3.4'],
        'ttl': 0
    }
    response = api_client.post(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                record2_hash: record2
            }
        }),
        content_type='application/merge-patch+json'
    )
    assert response.data['records'] == {
        'ttl': ['Ensure this value is greater than or equal to 300.']
    }


@pytest.mark.django_db
def test_change_name_of_record(api_client, zone):
    zone, client = zone
    record2_hash = '7Q45ew5E0vOMq'
    record2 = {
        'name': 'altceva',
        'type': 'A',
        'values': ['1.1.1.1'],
        'ttl': 300
    }
    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                record2_hash: record2
            }
        }),
        content_type='application/merge-patch+json'
    )
    assert response.data['records']['geE2gXwXDmx7D'] == record2
    assert record2_hash not in response.data['records']


@pytest.mark.django_db
def test_change_ttl_of_record(api_client, zone):
    zone, client = zone
    record2_hash = '7Q45ew5E0vOMq'
    record2 = {
        'name': 'test',
        'type': 'A',
        'values': ['1.1.1.1'],
        'ttl': 550
    }
    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                record2_hash: record2
            }
        }),
        content_type='application/merge-patch+json'
    )
    assert response.data['records']['7Q45ew5E0vOMq'] == record2
    # assert record2 in client.list_resource_record_sets(zone.route53_id)['ResourceRecordSets']


@pytest.mark.django_db
def test_change_type_of_record(api_client, zone):
    zone, client = zone
    record2_hash = '7Q45ew5E0vOMq'
    record2 = {
        'name': 'altceva',
        'type': 'CNAME',
        'values': ['new.presslabs.net'],
        'ttl': 300
    }
    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                record2_hash: record2
            }
        }),
        content_type='application/merge-patch+json'
    )
    assert response.data['records']['nBl2zBJW83zVP'] == record2
    assert record2_hash not in response.data['records']


@pytest.mark.django_db
def test_hidden_records(api_client, zone):
    zone, client = zone
    zone.add_record({
        'name': '{}_ceva'.format(m.RECORD_PREFIX),
        'ttl': 300,
        'type': 'A',
        'values': ['1.2.3.4']
    })
    zone.save()
    response = api_client.get(
        '/zones/%s/' % zone.id,
    )
    assert strip_ns_and_soa(response.data['records']) == {
        '7Q45ew5E0vOMq': {
            'values': ['1.1.1.1'],
            'name': 'test',
            'ttl': 300,
            'type': 'A',
        }
    }


@pytest.mark.django_db
def test_alias_records(api_client, zone):
    zone, client = zone
    zone.add_record({
        'name': 'ceva',
        'type': 'A',
        'AliasTarget': {
            'HostedZoneId': zone.route53_zone.id,
            'DNSName': 'test',
            'EvaluateTargetHealth': False
        },
    })
    zone.save()
    response = api_client.get(
        '/zones/%s/' % zone.id,
    )
    assert strip_ns_and_soa(response.data['records']) == {
        '7Q45ew5E0vOMq': {
            'values': ['1.1.1.1'],
            'name': 'test',
            'ttl': 300,
            'type': 'A',
        },
        '7VJVGlXjX3q66': {
            'name': 'ceva',
            'type': 'A',
            'values': ['ALIAS test.test-zinc.net.']
        }
    }


@pytest.mark.django_db
def test_validation_prefix(api_client, zone):
    zone, _ = zone
    response = api_client.post(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                'new': {
                    'name': '_zn_something',
                    'ttl': 300,
                    'type': 'CNAME',
                    'values': ['www.google.com']
                }
            }
        }),
        content_type='application/merge-patch+json'
    )

    assert response.data == {
        'records': [
            'Record _zn_something can\'t start with _zn. It\'s a reserved prefix.'
        ]
    }
