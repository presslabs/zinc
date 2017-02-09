# pylint: disable=no-member,unused-argument,protected-access,redefined-outer-name
import random
import string
from copy import deepcopy
from datetime import datetime

import botocore.exceptions
import pytest
from mock import patch

from dns import models as m
from dns.utils import route53
from rest_framework.test import APIClient


def random_ascii(length):
    return "".join(
        random.choice(string.ascii_letters) for _ in range(length)
    )


class CleanupClient:
    """Wraps real boto client and tracks zone and healthcheck creation, so it can clean up at the end"""
    def __init__(self, client):
        self._client = client
        self._zones = {}
        self._health_checks = {}

    def __getattr__(self, attr_name):
        return getattr(self._client, attr_name)

    def __hasattr__(self, attr_name):
        return hasattr(self._client, attr_name)

    def create_hosted_zone(self, **kwa):
        resp = self._client.create_hosted_zone(**kwa)
        zone_id = resp['HostedZone']['Id']
        self._zones[zone_id] = resp['HostedZone']['Name']
        return resp

    def delete_hosted_zone(self, Id, **kwa):
        resp = self._client.delete_hosted_zone(Id=Id, **kwa)
        self._zones.pop(Id)
        return resp

    def create_health_check(self, **kwa):
        resp = self._client.create_health_check(**kwa)
        check_id = resp['HealthCheck']['Id']
        self._health_checks[check_id] = resp['HealthCheck']
        return resp

    def delete_health_check(self, HealthCheckId, **kwa):
        resp = self._client.delete_health_check(HealthCheckId=HealthCheckId, **kwa)
        self._health_checks.pop(HealthCheckId)
        return resp

    def _cleanup_hosted_zones(self):
        for zone_id, zone_name in list(self._zones.items()):
            try:
                records = self.list_resource_record_sets(HostedZoneId=zone_id)
                for record in records['ResourceRecordSets']:
                    if record['Type'] == 'SOA' or (
                            record['Type'] == 'NS' and record['Name'] == zone_name):
                        # the SOA and the root NS can't be deleted, so we skip these
                        continue
                    try:
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
                    except botocore.exceptions.ClientError as excp:
                        print("Failed to delete record", record, excp.response['Error'])
                self._client.delete_hosted_zone(Id=zone_id)
            except botocore.exceptions.ClientError as excp:
                print("Failed to delete", zone_id, excp.response['Error'])
            del self._zones[zone_id]

    def _cleanup_health_checks(self):
        for healthcheck_id in self._health_checks.keys():
            try:
                self._client.delete_health_check(HealthCheckId=healthcheck_id)
            except botocore.exceptions.ClientError as excp:
                print("Failed to delete healthcheck", excp.response['Error'])

    def cleanup(self):
        self._cleanup_hosted_zones()
        self._cleanup_health_checks()


@pytest.fixture
def api_client():
    return APIClient()


class Moto:
    """"Mock boto"""

    def __init__(self):
        self._zones = {}
        self._health_checks = {}

    def create_hosted_zone(self, Name, CallerReference, HostedZoneConfig):
        # print("create_hosted_zone", Name, CallerReference, HostedZoneConfig)
        zone_id = "{}/{}/{}".format(random_ascii(4), random_ascii(4), random_ascii(4))
        self._zones[zone_id] = {}
        return {
            'HostedZone': {
                'Id': zone_id
            }
        }

    def create_health_check(self, CallerReference, HealthCheckConfig):
        check_id = random_ascii(8)
        check = {
            'HealthCheck': {
                'Id': check_id,
                'HealthCheckConfig': HealthCheckConfig,
            }
        }
        self._health_checks[check_id] = check
        return check

    def get_health_check(self, HealthCheckId):
        try:
            return self._health_checks[HealthCheckId]
        except KeyError:
            raise botocore.exceptions.ClientError()

    def cleanup(self):
        self._zones = {}
        self._health_checks = {}

    def delete_hosted_zone(self, Id):
        self._zones.pop(Id)

    def delete_health_check(self, HealthCheckId):
        self._health_checks.pop(HealthCheckId)

    @staticmethod
    def _remove_record(records, record):
        f_index = None
        for index, _record in enumerate(records):
            if ((_record['Name'] == record['Name']) and (_record['Type'] == record['Type'])):
                f_index = index
                break
        else:
            return
        records.pop(f_index)

    def change_resource_record_sets(self, HostedZoneId, ChangeBatch):
        zone = self._zones[HostedZoneId]
        records = zone.setdefault('ResourceRecordSets', [])

        for change in ChangeBatch['Changes']:
            if change['Action'] == 'DELETE':
                self._remove_record(records, change['ResourceRecordSet'])
            elif change['Action'] == 'UPSERT':
                self._remove_record(records, change['ResourceRecordSet'])
                records.append(change['ResourceRecordSet'])
            elif change['Action'] == 'CREATE':
                records.append(change['ResourceRecordSet'])
            else:
                raise AssertionError(change['Action'])

    def list_resource_record_sets(self, HostedZoneId=None):
        return self.response[HostedZoneId]

    @property
    def response(self):
        return deepcopy(self._zones)


@pytest.fixture(
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
        client.cleanup()
    request.addfinalizer(cleanup)
    return client


@pytest.fixture()
def zone(request, boto_client):
    client = boto_client

    caller_ref = 'zinc ref-fixture {}'.format(datetime.now())
    zone_name = 'test-zinc.net.'

    zone = client.create_hosted_zone(
        Name=zone_name,
        CallerReference=caller_ref,
        HostedZoneConfig={
            'Comment': 'zinc-fixture-%s' % random_ascii(6)
        }
    )

    zone_id = zone['HostedZone']['Id']

    client.change_resource_record_sets(
        HostedZoneId=zone_id,
        ChangeBatch={
            'Comment': 'zinc-fixture',
            'Changes': [
                {
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'Name': 'test.%s' % zone_name,
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
    return zone, client
