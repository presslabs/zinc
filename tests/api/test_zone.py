import pytest

from rest_framework.test import APIClient

from dns import models as m
from dns.utils.route53 import client


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_create_zone(api_client):
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

    #TODO: this needs to move to fixture cleanup
    client.delete_hosted_zone(Id=m.Zone.objects.first().route53_id)
