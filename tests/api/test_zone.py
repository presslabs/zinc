import pytest
from mock import patch

from rest_framework.test import APIClient

from dns import models as m
from dns.utils import route53


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

    def delete_hosted_zone(self, Id):
        pass

@pytest.fixture(
    # scope='module',
    params=[
        Moto,
        lambda: route53.client,
    ],
    ids=['fake_boto', 'with_aws']
)
def boto_client(request):
    client = request.param()
    patcher = patch('dns.utils.route53.client', client)
    patcher.start()
    def cleanup():
        patcher.stop()
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

    #TODO: this needs to move to fixture cleanup
    boto_client.delete_hosted_zone(Id=m.Zone.objects.first().route53_id)
