import pytest
from mock import patch

from rest_framework.test import APIClient

from dns import models as m
from dns.utils import route53
from tests.fixtures import CleanupClient


@pytest.fixture
def api_client():
    return APIClient()


class Moto:
    """"Mock boto"""
    def create_hosted_zone(self, **kwa):
        return {
            'HostedZone': {
                'Id': 'Fake/Fake/Fake'
            }
        }

    def _cleanup_hosted_zones(self):
        pass


@pytest.fixture(
    # scope='module',
    params=[
        Moto,
        lambda: CleanupClient(route53.client),
    ],
    ids=['fake_boto', 'with_aws']
)
def boto_client(request):
    client = request.param()
    patcher = patch('dns.utils.route53.client', client)
    patcher.start()
    def cleanup():
        patcher.stop()
        client._cleanup_hosted_zones()
    request.addfinalizer(cleanup)
    return client



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
