# pylint: disable=no-member,unused-argument,protected-access,redefined-outer-name
import uuid
import random
import string

from django.contrib.auth import get_user_model
import botocore.exceptions
import pytest
from mock import patch
from rest_framework.test import APIClient
from django_dynamic_fixture import G

from zinc import models as m
from zinc import route53


def random_ascii(length):
    return "".join(
        random.choice(string.ascii_letters) for _ in range(length)
    )


class CleanupClient:
    """
    Wraps real boto client and tracks zone and healthcheck creation, so it can clean up at the end
    """
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
        self._zones.pop(Id, None)
        return resp

    def create_health_check(self, **kwa):
        resp = self._client.create_health_check(**kwa)
        check_id = resp['HealthCheck']['Id']
        self._health_checks[check_id] = resp['HealthCheck']
        return resp

    def delete_health_check(self, HealthCheckId, **kwa):
        resp = self._client.delete_health_check(HealthCheckId=HealthCheckId, **kwa)
        self._health_checks.pop(HealthCheckId, None)
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
@pytest.mark.django_db
def api_client():
    user = G(get_user_model())
    client = APIClient(format='json')
    client.force_authenticate(user=user)
    return client


class FakePaginator:
    def __init__(self, client, op_name):
        self._client = client
        self._op_name = op_name

    def paginate(self, **kwargs):
        """return a one element list, so we can pretent to paginate"""
        return [getattr(self._client, self._op_name)(**kwargs)]


class Moto:
    """"Mock boto"""

    def __init__(self):
        self._zones = {}
        self._health_checks = {}
        self._health_checks_caller_reference = {}

    def get_paginator(self, op_name):
        return FakePaginator(self, op_name)

    def create_hosted_zone(self, Name, CallerReference, HostedZoneConfig):
        zone_id = "{}/{}/{}".format(random_ascii(4), random_ascii(4), random_ascii(4))
        self._zones[zone_id] = {}
        self.change_resource_record_sets(
            zone_id,
            {'Changes': [
                {
                    'ResourceRecordSet': {
                        'Name': Name,
                        'Type': 'NS',
                        'TTL': 1300,
                        'ResourceRecords': [
                            {
                                'Value': 'test_ns1.presslabs.net',
                            },
                            {
                                'Value': 'test_ns2.presslabs.net',
                            },
                        ]
                    },
                    'Action': 'CREATE'
                },
                {
                    'ResourceRecordSet': {
                        'Name': Name,
                        'Type': 'SOA',
                        'TTL': 1300,
                        'ResourceRecords': [
                            {
                                'Value': ('ns1.zincimple.com admin.zincimple.com '
                                          '2013022001 86400 7200 604800 300'),
                            }
                        ]
                    },
                    'Action': 'CREATE'
                }
            ]}
        )
        return {
            'HostedZone': {
                'Id': zone_id
            }
        }

    def create_health_check(self, CallerReference, HealthCheckConfig):
        if CallerReference in self._health_checks_caller_reference:
            check_id = self._health_checks_caller_reference[CallerReference]
            check = self._health_checks.get(check_id)
            if check is None or not(
                    check['HealthCheck']['HealthCheckConfig'].items() >= HealthCheckConfig.items()):
                raise botocore.exceptions.ClientError(
                    error_response={
                        'Error': {
                            'Code': 'HealthCheckAlreadyExists',
                            'Message': 'Fake Boto say: Y U reuse CallerReference?',
                            'Type': 'Sender'
                        },
                    },
                    operation_name='get_health_check',
                )
            else:
                return check
        check_id = random_ascii(8)
        check = {
            'HealthCheck': {
                'Id': check_id,
                'HealthCheckConfig': HealthCheckConfig,
            }
        }
        self._health_checks[check_id] = check
        self._health_checks_caller_reference[CallerReference] = check_id
        return check

    def get_health_check(self, HealthCheckId):
        try:
            return self._health_checks[HealthCheckId]
        except KeyError:
            raise botocore.exceptions.ClientError(
                error_response={
                    'Error': {
                        'Code': 'NoSuchHealthCheck',
                        'Message': ('A health check with id 9d7e44c2-72b9-42f2-b771-9216deb26ca1 '
                                    'does not exist.'),
                        'Type': 'Sender'
                    },
                },
                operation_name='get_health_check',
            )

    def get_hosted_zone(self, Id):
        try:
            return self._zones[Id]
        except KeyError:
            raise botocore.exceptions.ClientError(
                error_response={
                    'Error': {
                        'Code': 'NoSuchHostedZone',
                        'Message': ('No hosted zone found with id {}.'.format(Id)),
                        'Type': 'Sender'
                    },
                },
                operation_name='get_hosted_zone',
            )

    def cleanup(self):
        self._zones = {}
        self._health_checks = {}

    def delete_hosted_zone(self, Id):
        self._zones.pop(Id)

    def delete_health_check(self, HealthCheckId):
        self._health_checks.pop(HealthCheckId)

    def _add_record(self, zone_id, record):
        key = self._record_key(record)
        self._zones[zone_id][key] = record

    def _remove_record(self, zone_id, record):
        key = self._record_key(record)
        self._zones[zone_id].pop(key)

    @staticmethod
    def _reverse_url_tokens(url):
        return ".".join(reversed(url.split('.')))

    @staticmethod
    def _record_key(record={}, name=None, rtype=None):
        name = record['Name'] if name is None else name
        rtype = record['Type'] if rtype is None else rtype
        set_id = record.get('SetIdentifier')
        # turn a.example.com -> com.example.a
        name = Moto._reverse_url_tokens(name)
        return (name, rtype, set_id)

    def _check_alias_target_valid(self, records, change, changes):
        record = change['ResourceRecordSet']
        target = record.get('AliasTarget')
        if target is None:
            return
        alias_key = (Moto._reverse_url_tokens(target['DNSName']), record['Type'])
        if not any((alias_key == record_key[:2]) for record_key in records):
            raise botocore.exceptions.ClientError(
                error_response={
                    'Error': {
                        'Code': 'InvalidChangeBatch',
                        'Message': ('{} Alias target doesn\'t exist {}, type {}.'.format(
                            record['Name'], target['DNSName'], record['Type'])),
                        'Type': 'Sender'
                    },
                },
                operation_name='change_resource_record_sets',
            )

    def _check_cname_clash(self, records, change, changes):
        record = change['ResourceRecordSet']
        r_type = record['Type']
        if r_type not in ('A', 'AAAA'):
            return

        clash_key = (self._reverse_url_tokens(record['Name']), 'CNAME')
        if any((clash_key == record_key[:2]) for record_key in records):
            raise botocore.exceptions.ClientError(
                error_response={
                    'Error': {
                        'Code': 'InvalidChangeBatch',
                        'Message': (
                            "Can't create record {} of type {}, conflicts with a CNAME".format(
                                record['Name'], record['Type'])),
                        'Type': 'Sender'
                    },
                },
                operation_name='change_resource_record_sets',
            )

    def _check_record_doesnt_exist(self, records, change, changes):
        record = change['ResourceRecordSet']
        existing = records.keys()
        if self._record_key(record) in existing:
            raise botocore.exceptions.ClientError(
                error_response={
                    'Error': {
                        'Code': 'InvalidChangeBatch',
                        'Message': (
                            "Record {} of type {} already exists".format(
                                record['Name'], record['Type'])),
                        'Type': 'Sender'
                    },
                },
                operation_name='change_resource_record_sets',
            )

    def change_resource_record_sets(self, HostedZoneId, ChangeBatch):
        records = self._zones[HostedZoneId]

        changes = ChangeBatch['Changes']
        for change in changes:
            record_set = change['ResourceRecordSet']
            if change['Action'] == 'DELETE':
                self._remove_record(HostedZoneId, record_set)
            elif change['Action'] == 'UPSERT':
                if self._record_key(record_set) in records:
                    self._remove_record(HostedZoneId, record_set)
                self._check_cname_clash(records, change, changes)
                self._check_alias_target_valid(records, change, changes)
                self._add_record(HostedZoneId, record_set)
            elif change['Action'] == 'CREATE':
                self._check_alias_target_valid(records, change, changes)
                self._check_cname_clash(records, change, changes)
                self._check_record_doesnt_exist(records, change, changes)
                self._add_record(HostedZoneId, record_set)
            else:
                raise AssertionError(change['Action'])

    def list_resource_record_sets(self, HostedZoneId=None):
        """
        Return record sets in order.

        See boto3 documenation:
        http://boto3.readthedocs.io/en/latest/reference/services/route53.html#Route53.Client.list_resource_record_sets
        """
        try:
            zone = self._zones[HostedZoneId]
        except KeyError:
            raise botocore.exceptions.ClientError(
                error_response={
                    'Error': {
                        'Code': 'NoSuchHostedZone',
                        'Message': ('No hosted zone found with id {}.'.format(HostedZoneId)),
                        'Type': 'Sender'
                    },
                },
                operation_name='list_resource_record_sets',
            )
        records = [v for (k, v) in sorted(list(zone.items()))]
        return {'ResourceRecordSets': records}


@pytest.fixture(
    params=[
        Moto,
        lambda: CleanupClient(route53.client.get_client()),
    ],
    ids=['fake_boto', 'with_aws']
)
def boto_client(request):
    client = request.param()
    patcher = patch('zinc.route53.client._client', client)
    patcher.start()

    def cleanup():
        patcher.stop()
        client.cleanup()
    request.addfinalizer(cleanup)
    return client


@pytest.fixture()
def zone(request, boto_client):
    client = boto_client

    caller_ref = str(uuid.uuid4())
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
                },
            ]
        }
    )
    zone = m.Zone(root=zone_name, route53_id=zone_id, caller_reference=caller_ref)
    zone.save()
    return zone
