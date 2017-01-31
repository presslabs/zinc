# pylint: disable=no-member,unused-argument,protected-access,redefined-outer-name
import random
import string
from mock import patch
from datetime import datetime

import pytest
import botocore
from rest_framework.test import APIClient

from dns import models as m
from dns.utils import route53


class CleanupClient:
    """Wraps real boto3 client and tracks zone creation, so it can clean up at the end"""
    def __init__(self, client):
        self._client = client
        self._zone_ids = set([])

    def __getattr__(self, attr_name):
        return getattr(self._client, attr_name)

    def __hasattr__(self, attr_name):
        return hasattr(self._client, attr_name)

    def create_hosted_zone(self, **kwa):
        resp = self._client.create_hosted_zone(**kwa)
        zone_id = resp['HostedZone']['Id']
        self._zone_ids.add(zone_id)
        return resp

    def _cleanup_hosted_zones(self):
        for zone_id in self._zone_ids:
            try:
                records = self.list_resource_record_sets(HostedZoneId=zone_id)
                for record in records['ResourceRecordSets']:
                    if record['Type'] not in ('NS', 'SOA'):
                        self.change_resource_record_sets(
                            HostedZoneId=zone_id,
                            ChangeBatch={
                                'Comment': 'zinc-fixture',
                                'Changes': [
                                    {
                                        'Action': 'DELETE',
                                        'ResourceRecordSet': record
                                    },
                                ]
                            })

                self._client.delete_hosted_zone(Id=zone_id)
            except botocore.exceptions.ClientError as excp:
                print("Failed to delete", zone_id, excp.response['Error']['Code'])


@pytest.fixture
def api_client():
    return APIClient()


class Moto:
    """"Mock boto"""

    def __init__(self):
        self.response = {}

    def create_hosted_zone(self, **kwa):
        return {
            'HostedZone': {
                'Id': 'Fake/Fake/Fake'
            }
        }

    def _cleanup_hosted_zones(self):
        pass

    def set_route53_response(self, Id, response):
        self.response.update({Id: response})

    def delete_hosted_zone(self, Id=None):
        pass

    def change_resource_record_sets(self, HostedZoneId, ChangeBatch):
        for change in ChangeBatch['Changes']:
            if change['Action'] == 'DELETE':
                self.response.update({HostedZoneId: {}})
            elif change['Action'] == 'CREATE':
                self.response.update({HostedZoneId: {
                    'ResourceRecordSets': [change['ResourceRecordSet']]
                }})
            else:
                records = self.response[HostedZoneId]['ResourceRecordSets']
                self.response.update({HostedZoneId: {
                    'ResourceRecordSets': records + [change['ResourceRecordSet']]
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


@pytest.fixture()
def zone(request, boto_client):
    client = boto_client

    caller_ref = 'zinc ref-fixture {}'.format(datetime.now())
    zone_name = 'test-zinc.net'

    zone = client.create_hosted_zone(
            Name=zone_name,
            CallerReference=caller_ref,
            HostedZoneConfig={
                'Comment': 'zinc-fixture-%s' % "".join(
                    random.choice(string.ascii_letters) for _ in range(6)
                )
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
                        'Name': 'test.%s.' % zone_name,
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
    zone = m.Zone(root=zone_name, route53_id=zone_id, caller_reference=caller_ref)
    zone.save()
    return zone
