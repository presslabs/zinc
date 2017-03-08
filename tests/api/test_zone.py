# pylint: disable=no-member,unused-argument,protected-access,redefined-outer-name
import pytest

from botocore.exceptions import ClientError
from django_dynamic_fixture import G


from tests.fixtures import api_client, boto_client, zone  # noqa: F401
from tests.utils import strip_ns_and_soa, get_test_record

from zinc import models as m


@pytest.mark.django_db
def test_create_zone(api_client, boto_client):
    root = 'example.com.presslabs.com.'
    resp = api_client.post(
        '/zones',
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
        '/zones',
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

    response = api_client.get('/zones')

    assert [result['url'] for result in response.data] == [
        "http://testserver/zones/{}".format(zone.id) for zone in zones]
    assert ([(zone.id, zone.root, zone.dirty, zone.route53_zone.id) for zone in zones] ==
            [(zone['id'], zone['root'], zone['dirty'], zone['route53_id'])
             for zone in response.data])


@pytest.mark.django_db
def test_detail_zone(api_client, zone):
    response = api_client.get(
        '/zones/%s' % zone.id,
    )
    assert strip_ns_and_soa(response.data['records']) == [
        get_test_record(zone)
    ]
    assert response.data['route53_id'] == zone.route53_id
    assert response.data['dirty'] is False


@pytest.mark.django_db
def test_delete_a_zone(api_client, zone, boto_client):
    response = api_client.delete(
        '/zones/%s' % zone.id
    )

    with pytest.raises(ClientError) as excp_info:
        boto_client.get_hosted_zone(Id=zone.route53_id)
    assert excp_info.value.response['Error']['Code'] == 'NoSuchHostedZone'
    assert m.Zone.objects.filter(pk=zone.pk).count() == 0
    assert not response.data


@pytest.mark.django_db
def test_policy_record_create_more_values(api_client, zone):
    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data={
            'name': '@',
            'type': 'CNAME',
            'ttl': 300,
            'values': ['test1.com', 'test2.com']
        }
    )
    assert response.status_code == 400
    assert response.data == {
        'values': [
            'Only one value can be specified for CNAME records.'
        ]
    }
