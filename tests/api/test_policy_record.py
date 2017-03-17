# pylint: disable=no-member,unused-argument,protected-access,redefined-outer-name
import pytest

from django_dynamic_fixture import G

from tests.fixtures import api_client, boto_client, zone  # noqa: F401
from tests.utils import (strip_ns_and_soa, hash_policy_record,
                         get_test_record, create_ip_with_healthcheck)
from zinc import models as m
from zinc.route53 import get_local_aws_regions


regions = get_local_aws_regions()


def get_policy_record(policy_record, dirty=False, managed=False):
    return {
        'id': hash_policy_record(policy_record),
        'name': policy_record.name,
        'fqdn': ('{}.{}'.format(policy_record.name, policy_record.zone.root)
                 if policy_record.name != '@' else policy_record.zone.root),
        'type': 'POLICY_ROUTED',
        'values': [str(policy_record.policy.id)],
        'ttl': None,
        'dirty': dirty,
        'managed': managed,
        'url': 'http://testserver/zones/{}/records/{}'.format(
            policy_record.zone.id,
            hash_policy_record(policy_record))
    }


@pytest.mark.django_db
def test_policy_record_get(api_client, zone):
    policy = G(m.Policy)
    ip = create_ip_with_healthcheck()
    G(m.PolicyMember, policy=policy, region=regions[0], ip=ip)
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='@')
    policy_record.apply_record()

    response = api_client.get(
        '/zones/%s' % zone.id
    )

    assert strip_ns_and_soa(response.data['records']) == [
        get_test_record(zone),
        get_policy_record(policy_record),
    ]


@pytest.mark.django_db
def test_policy_record_create(api_client, zone):
    policy = G(m.Policy)
    G(m.PolicyMember, policy=policy, region=regions[0])

    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data={
            'name': '@',
            'type': 'POLICY_ROUTED',
            'values': [str(policy.id)],
        }
    )

    pr = m.PolicyRecord.objects.get(name='@', zone=zone)
    assert response.data == get_policy_record(pr, dirty=True)


@pytest.mark.django_db
def test_policy_record_update_policy(api_client, zone):
    policy = G(m.Policy)
    new_policy = G(m.Policy)

    G(m.PolicyMember, policy=policy, region=regions[0])

    policy_record = G(m.PolicyRecord, zone=zone, name='@', policy=policy)

    response = api_client.patch(
        '/zones/%s/records/%s' % (zone.id, get_policy_record(policy_record)['id']),
        data={
            'values': [str(new_policy.id)],
        }
    )

    pr = m.PolicyRecord.objects.get(name='@', zone=zone)
    assert pr.dirty is True
    assert pr.id == policy_record.id
    assert response.data == get_policy_record(pr, dirty=True)


@pytest.mark.django_db
def test_policy_record_delete(api_client, zone):
    policy = G(m.Policy)
    G(m.PolicyMember, policy=policy, region=regions[0])

    policy_record = G(m.PolicyRecord, zone=zone, name='@', policy=policy)

    response = api_client.delete(
        '/zones/%s/records/%s' % (zone.id, get_policy_record(policy_record)['id'])
    )

    pr = m.PolicyRecord.objects.get(name='@', zone=zone)
    assert response.status_code == 204, response.data
    assert str(pr.policy.id) == str(policy.id)
    assert pr.dirty is True
    assert pr.deleted is True
    assert pr.id == policy_record.id


@pytest.mark.django_db
def test_policy_record_get_more_than_one(api_client, zone):
    policy = G(m.Policy)
    ip = create_ip_with_healthcheck()
    G(m.PolicyMember, policy=policy, region=regions[0], ip=ip)
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='@')
    policy_record.apply_record()

    policy_record_2 = G(m.PolicyRecord, zone=zone, policy=policy, name='www')
    policy_record_2.apply_record()

    response = api_client.get(
        '/zones/%s' % zone.id
    )

    result = strip_ns_and_soa(response.data['records'])
    assert result == [
        get_test_record(zone),
        get_policy_record(policy_record),
        get_policy_record(policy_record_2),
    ]


@pytest.mark.django_db
def test_policy_record_create_more_than_one(api_client, zone):
    policy = G(m.Policy)
    ip1 = create_ip_with_healthcheck()
    ip2 = create_ip_with_healthcheck()
    G(m.PolicyMember, policy=policy, region=regions[0], ip=ip1)
    G(m.PolicyMember, policy=policy, region=regions[0], ip=ip2)

    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data={
            'name': '@',
            'type': 'POLICY_ROUTED',
            'values': [str(policy.id)],
        })
    response_2 = api_client.post(
        '/zones/%s/records' % zone.id,
        data={
            'name': 'test',
            'type': 'POLICY_ROUTED',
            'values': [str(policy.id)]
        })

    pr = m.PolicyRecord.objects.get(name='@', zone=zone)
    pr_2 = m.PolicyRecord.objects.get(name='test', zone=zone)
    assert response.data == get_policy_record(pr, dirty=True)
    assert response_2.data == get_policy_record(pr_2, dirty=True)


@pytest.mark.django_db
def test_policy_record_create_no_policy(api_client, zone):
    policy = G(m.Policy)
    G(m.PolicyMember, policy=policy, region=regions[0])

    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data={
            'name': '@',
            'type': 'POLICY_ROUTED',
            'values': ['10412ecd-f4ac-4025-94c8-e4750750b940'],
        }
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_policy_record_create_more_values(api_client, zone):
    policy = G(m.Policy)
    G(m.PolicyMember, policy=policy, region=regions[0])

    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data={
            'name': '@',
            'type': 'POLICY_ROUTED',
            'values': ['10412ecd-f4ac-4025-94c8-e4750750b940', '2346321345'],
        }
    )
    assert response.status_code == 400
    assert response.data == {
        'values': [
            'Only one value can be specified for POLICY_ROUTED records.'
        ]
    }


@pytest.mark.django_db
def test_create_policy_routed_if_cname_exists_should_fail(zone, api_client, boto_client):
    boto_client.change_resource_record_sets(
        HostedZoneId=zone.route53_zone.id,
        ChangeBatch={
            'Comment': 'zinc-fixture',
            'Changes': [
                {
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'Name': 'www.%s' % zone.root,
                        'Type': 'CNAME',
                        'TTL': 300,
                        'ResourceRecords': [
                            {
                                'Value': 'google.com',
                            }
                        ]
                    }
                },
            ]
        }
    )

    policy = G(m.Policy)
    region = get_local_aws_regions()[0]
    region2 = get_local_aws_regions()[1]
    ip = create_ip_with_healthcheck()
    G(m.PolicyMember, policy=policy, region=region, ip=ip)
    G(m.PolicyMember, policy=policy, region=region2, ip=ip)

    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data={
            'name': 'www',
            'type': 'POLICY_ROUTED',
            'values': [str(policy.id)]
        })
    with pytest.raises(m.PolicyRecord.DoesNotExist):
        m.PolicyRecord.objects.get(name='www', zone=zone)
    assert response.data['name'] == ['A CNAME record of the same name already exists.']
