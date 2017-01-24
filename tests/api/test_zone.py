# pylint: disable=no-member,unused-argument,protected-access,redefined-outer-name
import pytest
import json
from datetime import datetime

from django_dynamic_fixture import G
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
    response = {}

    def create_hosted_zone(self, **kwa):
        return {
            'HostedZone': {
                'Id': 'Fake/Fake/Fake'
            }
        }

    def _cleanup_hosted_zones(self):
        pass

    def set_route53_response(self,Id, response):
        self.response.update({Id: response})

    def delete_hosted_zone(self, Id=None):
        pass

    def change_resource_record_sets(self, HostedZoneId, ChangeBatch):
        for change in ChangeBatch['Changes']:
            self.response.update({HostedZoneId: {
                'ResourceRecordSets': [change['ResourceRecordSet']]
            }})

    def list_resource_record_sets(self, HostedZoneId=None):
        return self.response[HostedZoneId]


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


@pytest.fixture(
    params=[
        Moto,
        lambda: CleanupClient(route53.client),
    ],
    ids=['fake_boto', 'with_aws']
)
def zone(request):
    client = request.param()

    caller_ref = 'zinc ref-fixture {}'.format(datetime.now())
    zone = client.create_hosted_zone(
            Name='test-zinc.net',
            CallerReference=caller_ref,
            HostedZoneConfig={
                'Comment': 'zinc-fixture'
            }
        )

    zone_id = zone['HostedZone']['Id'].split('/')[2]


    client.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            'Comment': 'zinc-fixture',
            'Changes': [
                {
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'Name': 'test.test-zinc.net',
                        'Type': 'A',
                        'TTL': 300,
                        'ResourceRecords': [
                            {
                                'Value': '1.1.1.1',
                            }
                        ]
                    }
                }
            ]
        }
    )
    patcher = patch('dns.utils.route53.client', client)
    patcher.start()
    def cleanup():
        patcher.stop()

        client._cleanup_hosted_zones()
    request.addfinalizer(cleanup)
    zone = m.Zone(root='test-zinc.net', route53_id=zone_id, caller_reference=caller_ref)
    zone.save()
    return zone





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
    boto_client.set_route53_response(zone.route53_id, {
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
    })
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


@pytest.mark.django_db
def test_zone_patch_with_records(api_client, zone):
    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                '7Q45ew5E0vOMq': {
                    'values': ['2.2.2.2'],
                    'type': 'A',
                    'ttl': 300,
                    'name': 'ceva'
                }
            }
        }),
        content_type='application/merge-patch+json'
    )
    print(response.data)
