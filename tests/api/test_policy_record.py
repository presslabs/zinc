# pylint: disable=no-member,unused-argument,protected-access,redefined-outer-name
import pytest
import json

from django_dynamic_fixture import G
from django.core.exceptions import ObjectDoesNotExist

from tests.fixtures import api_client, boto_client, zone
from tests.utils import strip_ns_and_soa
from dns import models as m
from dns.utils.route53 import get_local_aws_regions


regions = get_local_aws_regions()


@pytest.mark.django_db
def test_policy_record_get(api_client, zone):
    zone, _ = zone
    policy = G(m.Policy)
    G(m.PolicyMember, policy=policy, region=regions[0])
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='@')
    policy_record.apply_record()

    response = api_client.get(
        '/zones/%s/' % zone.id
    )

    assert strip_ns_and_soa(response.data['records']) == {
        'GW5Xxvn9kYvmd': {
            'name': 'test',
            'type': 'A',
            'ttl': 300,
            'dirty': False,
            'values': ['1.1.1.1']
        },
        str(policy_record.id): {
            'name': '@',
            'type': 'POLICY_ROUTED',
            'values': [str(policy.id)],
            'dirty': False
        },
    }


@pytest.mark.django_db
def test_policy_record_create(api_client, zone):
    zone, _ = zone
    policy = G(m.Policy)
    G(m.PolicyMember, policy=policy, region=regions[0])

    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                'new': {
                    'name': '@',
                    'type': 'POLICY_ROUTED',
                    'values': [str(policy.id)],
                }
            }
        }),
        content_type='application/merge-patch+json'
    )

    pr = m.PolicyRecord.objects.get(name='@', zone=zone)
    assert strip_ns_and_soa(response.data['records']) == {
        'GW5Xxvn9kYvmd': {
            'name': 'test',
            'type': 'A',
            'ttl': 300,
            'dirty': False,
            'values': ['1.1.1.1']
        },
        str(pr.id): {
            'name': '@',
            'type': 'POLICY_ROUTED',
            'dirty': True,
            'values': [str(policy.id)]
        },
    }


@pytest.mark.django_db
def test_policy_record_update_policy(api_client, zone):
    zone, _ = zone
    policy = G(m.Policy)
    new_policy = G(m.Policy)

    G(m.PolicyMember, policy=policy, region=regions[0])

    policy_record = G(m.PolicyRecord, zone=zone, name='@', policy=policy)

    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                str(policy_record.id): {
                    'name': '@',
                    'type': 'POLICY_ROUTED',
                    'values': [str(new_policy.id)],
                }
            }
        }),
        content_type='application/merge-patch+json'
    )

    pr = m.PolicyRecord.objects.get(name='@', zone=zone)
    assert pr.dirty is True
    assert pr.id == policy_record.id
    assert strip_ns_and_soa(response.data['records']) == {
        'GW5Xxvn9kYvmd': {
            'name': 'test',
            'type': 'A',
            'ttl': 300,
            'dirty': False,
            'values': ['1.1.1.1']
        },
        str(pr.id): {
            'name': '@',
            'type': 'POLICY_ROUTED',
            'dirty': True,
            'values': [str(new_policy.id)]
        },
    }


@pytest.mark.django_db
def test_policy_record_delete(api_client, zone):
    zone, _ = zone
    policy = G(m.Policy)
    G(m.PolicyMember, policy=policy, region=regions[0])

    policy_record = G(m.PolicyRecord, zone=zone, name='@', policy=policy)

    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                str(policy_record.id): None
            }
        }),
        content_type='application/merge-patch+json'
    )

    pr = m.PolicyRecord.objects.get(name='@', zone=zone)
    assert str(pr.policy.id) == str(policy.id)
    assert pr.dirty is True
    assert pr.deleted is True
    assert pr.id == policy_record.id
    assert strip_ns_and_soa(response.data['records']) == {
        'GW5Xxvn9kYvmd': {
            'name': 'test',
            'type': 'A',
            'ttl': 300,
            'dirty': False,
            'values': ['1.1.1.1']
        },
        str(pr.id): {
            'name': '@',
            'type': 'POLICY_ROUTED',
            'values': [str(policy.id)],
            'dirty': True,
        },
    }


@pytest.mark.django_db
def test_policy_record_get_more_than_one(api_client, zone):
    zone, _ = zone
    policy = G(m.Policy)
    G(m.PolicyMember, policy=policy, region=regions[0])
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='@')
    policy_record.apply_record()

    policy_record_2 = G(m.PolicyRecord, zone=zone, name='test')
    policy_record_2.apply_record()

    response = api_client.get(
        '/zones/%s/' % zone.id
    )

    assert strip_ns_and_soa(response.data['records']) == {
        'GW5Xxvn9kYvmd': {
            'name': 'test',
            'type': 'A',
            'ttl': 300,
            'dirty': False,
            'values': ['1.1.1.1']
        },
        str(policy_record.id): {
            'name': '@',
            'type': 'POLICY_ROUTED',
            'values': [str(policy.id)],
            'dirty': False
        },
        str(policy_record_2.id): {
            'name': 'test',
            'type': 'POLICY_ROUTED',
            'values': [str(policy_record_2.policy.id)],
            'dirty': False
        },
    }


@pytest.mark.django_db
def test_policy_record_create_more_than_one(api_client, zone):
    zone, _ = zone
    policy = G(m.Policy)
    G(m.PolicyMember, policy=policy, region=regions[0])
    G(m.PolicyMember, policy=policy, region=regions[0])

    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                'new': {
                    'name': '@',
                    'type': 'POLICY_ROUTED',
                    'values': [str(policy.id)],
                },
                'new2': {
                    'name': 'test',
                    'type': 'POLICY_ROUTED',
                    'values': [str(policy.id)]
                }
            }
        }),
        content_type='application/merge-patch+json'
    )

    pr = m.PolicyRecord.objects.get(name='@', zone=zone)
    pr_2 = m.PolicyRecord.objects.get(name='test', zone=zone)
    assert strip_ns_and_soa(response.data['records']) == {
        'GW5Xxvn9kYvmd': {
            'name': 'test',
            'type': 'A',
            'ttl': 300,
            'dirty': False,
            'values': ['1.1.1.1']
        },
        str(pr.id): {
            'name': '@',
            'type': 'POLICY_ROUTED',
            'dirty': True,
            'values': [str(policy.id)]
        },
        str(pr_2.id): {
            'name': 'test',
            'type': 'POLICY_ROUTED',
            'dirty': True,
            'values': [str(policy.id)]
        },
    }


@pytest.mark.django_db
def test_policy_record_create_no_policy(api_client, zone):
    zone, _ = zone
    policy = G(m.Policy)
    G(m.PolicyMember, policy=policy, region=regions[0])

    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                'new': {
                    'name': '@',
                    'type': 'POLICY_ROUTED',
                    'values': ['10412ecd-f4ac-4025-94c8-e4750750b940'],
                }
            }
        }),
        content_type='application/merge-patch+json'
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_policy_record_create_more_values(api_client, zone):
    zone, _ = zone
    policy = G(m.Policy)
    G(m.PolicyMember, policy=policy, region=regions[0])

    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                'new': {
                    'name': '@',
                    'type': 'POLICY_ROUTED',
                    'values': ['10412ecd-f4ac-4025-94c8-e4750750b940', '2346321345'],
                }
            }
        }),
        content_type='application/merge-patch+json'
    )

    assert response.status_code == 400
    assert response.data == {
        'records': {
            'non_field_errors': [
                'For POLICY_ROUTED record values list should contain just one element.'
            ]
        }
    }
