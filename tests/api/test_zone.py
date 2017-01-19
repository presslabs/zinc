# pylint: disable=E1101,W0613,W0621
import pytest
from mock import patch

from rest_framework.test import APIClient

from dns import models as m
from dns.utils import route53
from tests.fixtures import CleanupClient

from django_dynamic_fixture import G


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

    def delete_hosted_zone(self, Id=None):
        pass

    def change_resource_record_sets(self, *args, **kwargs):
        pass

    def list_resource_record_sets(self, HostedZoneId=None):
        return {
            'IsTruncated': False,
            'MaxItems': '100',
            'ResourceRecordSets': [{
                'Name': 'testing.com.',
                'ResourceRecords': [
                    {'Value': 'ns-1449.awsdns-53.org.'},
                    {'Value': 'ns-689.awsdns-22.net.'},
                    {'Value': 'ns-1584.awsdns-06.co.uk.'},
                    {'Value': 'ns-33.awsdns-04.com.'}
                ],
                'TTL': 172800,
                'Type': 'NS'
            },
            {
                'Name': 'testing.com.',
                'ResourceRecords': [
                    {'Value': ('ns-1449.awsdns-53.org. awsdns-hostmaster'
                               '.amazon.com. 1 7200 900 1209600 86400')}
                ],
                'TTL': 900,
                'Type': 'SOA'
            }],
            'ResponseMetadata': {
                'HTTPHeaders': {'content-length': '902',
                'content-type': 'text/xml',
                'date': 'Thu, 19 Jan 2017 16:30:47 GMT',
                'x-amzn-requestid': 'a24c16ba-de64-11e6-a56d-97d11b971af4'},
                'HTTPStatusCode': 200,
                'RequestId': 'a24c16ba-de64-11e6-a56d-97d11b971af4',
                'RetryAttempts': 0
            }
        } if HostedZoneId == 'ZOXRVCT8C8119' else {}


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


@pytest.mark.django_db
def test_list_zones(api_client, boto_client):
    G(m.Zone, root='1.example.com')
    G(m.Zone, root='2.example.com')
    response = api_client.get('/zones/')

    assert 'url' in response.data[0]
    assert (list(m.Zone.objects.all().values_list('id', 'root')) ==
            [(z['id'], z['root']) for z in response.data])


@pytest.mark.django_db
def test_detail_zone(api_client, boto_client):
    zone = G(m.Zone, root='1.example.com')
    response = api_client.get('/zones/%s/' % zone.id)

    assert response.data['root'] == zone.root
    assert response.data['records'] == {}

@pytest.mark.django_db
def test_detail_zone_with_real_zone(api_client, boto_client):
    # zone already exists in AWS.
    zone = G(m.Zone, root='testing.com', route53_id='ZOXRVCT8C8119')
    response = api_client.get(
        '/zones/%s/' % zone.id,
    )

    assert response.data['records'] == {
        "8nyJG1546Q8QL": {
            "values": [
                ("ns-1449.awsdns-53.org. awsdns-hostmaster"
                 ".amazon.com. 1 7200 900 1209600 86400")
            ],
            "type": "SOA",
            "ttl": 900,
            "name": "@"
        },
        "YxXyP8853e8bO": {
            "values": [
                "ns-1449.awsdns-53.org.",
                "ns-689.awsdns-22.net.",
                "ns-1584.awsdns-06.co.uk.",
                "ns-33.awsdns-04.com."
            ],
            "type": "NS",
            "ttl": 172800,
            "name": "@"
        }
    }
