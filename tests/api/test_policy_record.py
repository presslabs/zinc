# pylint: disable=no-member,unused-argument,protected-access,redefined-outer-name
import pytest
import json

from django_dynamic_fixture import G
from django.core.exceptions import ObjectDoesNotExist

from tests.fixtures import api_client, boto_client, zone
from dns import models as m
from dns.utils.route53 import get_local_aws_regions


def strip_ns_and_soa(records):
    """The NS and SOA records are managed by AWS, so we won't care about them in tests"""
    return {
        record_id: record
        for record_id, record in records.items()
        if not (record['type'] in ('NS', 'SOA') and record['name'] == '@')
    }


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
        '7Q45ew5E0vOMq': {
            'name': 'test',
            'type': 'A',
            'ttl': 300,
            'values': ['1.1.1.1']
        },
        '0vl125rRM4wzJ': {
            'name': '@',
            'type': 'POLICY_ROUTED'
        },
    }


@pytest.mark.django_db
@pytest.mark.xfail
def test_policy_record_post(api_client, zone):
    zone, _ = zone
    policy = G(m.Policy)

    G(m.PolicyMember, policy=policy, region=regions[0])

    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='@')

    policy_record.apply_record()

    response = api_client.patch(
        '/zones/%s/' % zone.id,
        data=json.dumps({
            'records': {
                'new': {
                    'name': '@',
                    'type': 'POLICY_ROUTED',
                    'values': str(policy.id)  # TODO: implement this.
                }
            }
        }),
        content_type='application/merge-patch+json'
    )

    assert strip_ns_and_soa(response.data['records']) == {
        '7Q45ew5E0vOMq': {
            'name': 'test',
            'type': 'A',
            'ttl': 300,
            'values': ['1.1.1.1']
        },
        '0vl125rRM4wzJ': {
            'name': '@',
            'type': 'POLICY_ROUTED',
            'values': policy.id
        },
    }
