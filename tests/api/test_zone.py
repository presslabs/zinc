# pylint: disable=no-member,unused-argument,protected-access,redefined-outer-name
import pytest
import json

from botocore.exceptions import ClientError
from django_dynamic_fixture import G
from django.core.exceptions import ObjectDoesNotExist
from django.test import override_settings

from tests.fixtures import api_client, boto_client, zone
from tests.utils import (strip_ns_and_soa, hash_test_record, get_test_record,
                         aws_strip_ns_and_soa, record_to_aws)
from dns import models as m
from zinc.vendors.hashids import encode_record


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

    assert [result['url'] for result in response.data['results']] == [
        "http://testserver/zones/{}".format(zone.id) for zone in zones]
    assert ([(zone.id, zone.root, zone.dirty, zone.route53_zone.id) for zone in zones] ==
            [(zone['id'], zone['root'], zone['dirty'], zone['route53_id'])
             for zone in response.data['results']])


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
