# pylint: disable=no-member,unused-argument,protected-access,redefined-outer-name
import pytest
import json

from django_dynamic_fixture import G
from django.core.exceptions import ObjectDoesNotExist

from tests.fixtures import api_client, boto_client, zone
from dns import models as m


@pytest.mark.django_db
def test_create_zone(api_client, boto_client):
    root = 'example.com.presslabs.com'
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
def test_list_zones(api_client):
    zones = [G(m.Zone, root='1.example.com'),
             G(m.Zone, root='2.example.com')]
    response = api_client.get('/zones/')

    assert [result['url'] for result in response.data['results']] == [
        "http://testserver/zones/{}".format(zone.id) for zone in zones]
    assert (list(m.Zone.objects.all().values_list('id', 'root')) ==
            [(zone['id'], zone['root']) for zone in response.data['results']])


@pytest.mark.django_db
def test_detail_zone(api_client):
    zone = G(m.Zone, root='1.example.com')
    response = api_client.get('/zones/%s/' % zone.id)
    assert response.data['root'] == zone.root
    assert response.data['records'] == {}


@pytest.mark.django_db
def test_detail_zone_with_real_zone(api_client, zone):
    response = api_client.get(
        '/zones/%s/' % zone.id,
    )
    assert response.data['records']['7Q45ew5E0vOMq'] == {
        'values': ['1.1.1.1'],
        'name': 'test',
        'ttl': 300,
        'type': 'A'
    }


@pytest.mark.django_db
def test_zone_patch_with_records(api_client, zone):
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
    settings.CELERY_ALWAYS_EAGER = True
    response = api_client.delete(
        '/zones/%s/' % zone.id
    )

    with pytest.raises(ObjectDoesNotExist) as _:
        m.Zone.objects.get(pk=zone.id)

    assert not response.data


@pytest.mark.django_db
def test_add_record_without_values(api_client, zone):
    record2_hash = 'new'
    record2 = {
        'name': 'test',
        'ttl': 400,
        'type': 'A',
    }
    response = api_client.post(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records':{
                record2_hash: record2
            }
        }),
        content_type='application/merge-patch+json'
    )
    assert response.data['records'] == {'values': ['This field is required.']}


@pytest.mark.django_db
def test_add_record_without_ttl(api_client, zone):
    record2_hash = 'new'
    record2 = {
        'name': 'something',
        'type': 'A',
        'values': ['1.2.3.4'],
    }
    response = api_client.post(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records':{
                record2_hash: record2
            }
        }),
        content_type='application/merge-patch+json'
    )
    assert response.data['records'] == {'ttl': ['This field is required.']}


@pytest.mark.django_db
def test_add_record_ttl_invalid(api_client, zone):
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
            'records':{
                record2_hash: record2
            }
        }),
        content_type='application/merge-patch+json'
    )
    assert response.data['records'] == {'ttl': ['Ensure this value is greater than or equal to 300.']}
