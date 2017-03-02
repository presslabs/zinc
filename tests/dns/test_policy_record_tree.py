# pylint: disable=no-member,protected-access,redefined-outer-name
import pytest
from django_dynamic_fixture import G

from tests.fixtures import boto_client, zone  # noqa: F401
from tests.utils import create_ip_with_healthcheck
from dns import models as m
from dns.utils.route53 import get_local_aws_regions


def sort_key(record):
    return (record['Name'], record['Type'], record.get('SetIdentifier', None))


def strip_ns_and_soa(records, zone_root):
    """The NS and SOA records are managed by AWS, so we won't care about them in tests"""
    return sorted([
        record for record in records['ResourceRecordSets']
        if not(record['Type'] == 'SOA' or (record['Type'] == 'NS' and record['Name'] == zone_root))
    ], key=sort_key)


def policy_members_to_list(policy_members, policy_record):
    """
    Tries to reproduce what should be in AWS after a policy is applied.
    """
    zone = policy_record.zone
    policy = policy_record.policy
    policy_members = [pm for pm in policy_members if pm.policy == policy]
    regions = set([pm.region for pm in policy_members if pm.weight > 0])
    records_for_regions = [
        {
            'Name': '{}_{}.test-zinc.net.'.format(m.RECORD_PREFIX, policy.name),
            'Type': 'A',
            'AliasTarget': {
                'DNSName': '{}_{}.{}.test-zinc.net.'.format(m.RECORD_PREFIX, policy.name, region),
                'EvaluateTargetHealth': len(regions) > 1,
                'HostedZoneId': zone.route53_zone.id
            },
            'Region': region,
            'SetIdentifier': region,
        } for region in regions]
    records_for_policy_members = [
        {
            'Name': '{}_{}.{}.test-zinc.net.'.format(m.RECORD_PREFIX, policy.name,
                                                     policy_member.region),
            'Type': 'A',
            'ResourceRecords': [{'Value': policy_member.ip.ip}],
            'TTL': 30,
            'SetIdentifier': '{}-{}'.format(str(policy_member.id), policy_member.region),
            'Weight': policy_member.weight,
            'HealthCheckId': str(policy_member.ip.healthcheck_id),
        } for policy_member in policy_members if policy_member.weight > 0]
    the_policy_record = [
        {
            'Name': ('{}.{}'.format(policy_record.name, zone.root)
                     if policy_record.name != '@' else zone.root),
            'Type': 'A',
            'AliasTarget': {
                'HostedZoneId': zone.route53_zone.id,
                'DNSName': '{}_{}.{}'.format(m.RECORD_PREFIX, policy.name, zone.root),
                'EvaluateTargetHealth': False
            },
        }
    ] if len(regions) >= 1 else []

    return records_for_regions + records_for_policy_members + the_policy_record


@pytest.mark.django_db
def test_policy_member_to_list_helper():
    zone = G(m.Zone, route53_id='Fake')
    policy = G(m.Policy)
    region = get_local_aws_regions()[0]
    policy_members = [
        G(m.PolicyMember, policy=policy, region=region),
    ]
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy)
    result = policy_members_to_list(policy_members, policy_record)
    assert result == [
        {
            'AliasTarget': {
                'DNSName': '_zn_%s.%s.test-zinc.net.' % (policy.name, region),
                'EvaluateTargetHealth': False,
                'HostedZoneId': zone.route53_id
            },
            'Name': '_zn_%s.test-zinc.net.' % policy.name,
            'Region': region,
            'SetIdentifier': region,
            'Type': 'A'
        },
        {
            'Name': '_zn_%s.%s.test-zinc.net.' % (policy.name, region),
            'ResourceRecords': [{'Value': policy_members[0].ip.ip}],
            'SetIdentifier': '%s-%s' % (policy_members[0].id, region),
            'TTL': 30,
            'Type': 'A',
            'Weight': 10,
            'HealthCheckId': str(policy_members[0].ip.healthcheck_id),
        },
        {
            'AliasTarget': {
                'DNSName': '_zn_%s.%s' % (policy.name, zone.root),
                'EvaluateTargetHealth': False,
                'HostedZoneId': 'Fake'
            },
            'Name': '%s.%s' % (policy_record.name, zone.root),
            'Type': 'A',
        }
    ]


@pytest.mark.django_db
def test_policy_record_tree_builder(zone, boto_client):
    policy = G(m.Policy)
    region = get_local_aws_regions()[0]
    ip = create_ip_with_healthcheck()
    policy_members = [
        G(m.PolicyMember, policy=policy, region=region, ip=ip),
        G(m.PolicyMember, policy=policy, region=region, ip=ip),
    ]
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy)

    policy_record.apply_record()

    expected = [
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A',
        },
    ] + policy_members_to_list(policy_members, policy_record)

    assert strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id), zone.root
    ) == sorted(expected, key=sort_key)


@pytest.mark.django_db
def test_policy_record_tree_with_multiple_regions(zone, boto_client):
    policy = G(m.Policy)
    regions = get_local_aws_regions()
    ip = create_ip_with_healthcheck()
    policy_members = [
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip),
        G(m.PolicyMember, policy=policy, region=regions[1], ip=ip),
    ]
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy)

    policy_record.apply_record()

    expected = [
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A'
        },
    ] + policy_members_to_list(policy_members, policy_record)
    assert strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id), zone.root
    ) == sorted(expected, key=sort_key)


@pytest.mark.django_db
def test_policy_record_tree_with_multiple_regions_and_members(zone, boto_client):
    policy = G(m.Policy)
    regions = get_local_aws_regions()
    ip = create_ip_with_healthcheck()
    policy_members = [
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip),
        G(m.PolicyMember, policy=policy, region=regions[1], ip=ip),
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip),
        G(m.PolicyMember, policy=policy, region=regions[1], ip=ip),
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip),
        G(m.PolicyMember, policy=policy, region=regions[1], ip=ip),
    ]
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='@')

    policy_record.apply_record()

    expected = [
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A'
        },
    ] + policy_members_to_list(policy_members, policy_record)
    assert strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id), zone.root
    ) == sorted(expected, key=sort_key)


@pytest.mark.django_db
def test_policy_record_tree_within_members(zone, boto_client):
    policy = G(m.Policy)
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy)
    policy_record.apply_record()

    expected = [
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A'
        },
    ] + policy_members_to_list([], policy_record)

    assert strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id), zone.root
    ) == sorted(expected, key=sort_key)


@pytest.mark.django_db
def test_policy_record_tree_with_two_trees(zone, boto_client):
    policy = G(m.Policy)
    regions = get_local_aws_regions()
    ip = create_ip_with_healthcheck()
    ip2 = create_ip_with_healthcheck(ip='2.3.4.5')
    policy_members = [
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip2),
        G(m.PolicyMember, policy=policy, region=regions[1], ip=ip2),
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip2),
        G(m.PolicyMember, policy=policy, region=regions[1], ip=ip),
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip),
        G(m.PolicyMember, policy=policy, region=regions[1], ip=ip),
    ]

    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='@')
    policy_record2 = G(m.PolicyRecord, zone=zone, policy=policy, name='cdn')

    policy_record.apply_record()
    policy_record2.apply_record()

    expected = [
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A'
        },
        # this is a ordinary record. should be not modified.
        # we expect to have the policy tree created just once.
    ] + policy_members_to_list(policy_members, policy_record) + [
        {
            'Name': '{}.{}'.format(policy_record2.name, zone.root),
            'Type': 'A',
            'AliasTarget': {
                'HostedZoneId': zone.route53_zone.id,
                'DNSName': '{}_{}.{}'.format(m.RECORD_PREFIX, policy.name, zone.root),
                'EvaluateTargetHealth': False
            },
        }  # also we need to have the cdn policy_record ALIAS to the same policy.
    ]

    assert strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id), zone.root
    ) == sorted(expected, key=sort_key)


@pytest.mark.django_db
def test_policy_record_deletion(zone, boto_client):
    policy = G(m.Policy)
    region = get_local_aws_regions()[0]
    ip = create_ip_with_healthcheck()
    policy_members = [
        G(m.PolicyMember, policy=policy, region=region, ip=ip),
        G(m.PolicyMember, policy=policy, region=region, ip=ip),
    ]
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy)

    policy_record.apply_record()

    expected = [
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A'
        },
    ] + policy_members_to_list(policy_members, policy_record)

    assert strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id), zone.root
    ) == sorted(expected, key=sort_key)

    policy_record.delete_record()

    rrsets = boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id)
    assert strip_ns_and_soa(rrsets, zone.root) == [
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A'
        }
    ]


@pytest.mark.django_db
def test_policy_record_tree_deletion_with_two_trees(zone, boto_client):
    policy = G(m.Policy)
    regions = get_local_aws_regions()
    ip = create_ip_with_healthcheck()
    ip2 = create_ip_with_healthcheck(ip='2.3.4.5')
    policy_members = [
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip),
        G(m.PolicyMember, policy=policy, region=regions[1], ip=ip2),
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip2),
        G(m.PolicyMember, policy=policy, region=regions[1], ip=ip2),
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip),
        G(m.PolicyMember, policy=policy, region=regions[1], ip=ip),
    ]

    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='@')
    policy_record_to_delete = G(m.PolicyRecord, zone=zone, policy=policy, name='cdn')

    policy_record.apply_record()
    policy_record_to_delete.apply_record()

    policy_record_to_delete.delete_record()
    expected = [
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A'
        },  # this is a ordinary record. should be not modified.
        # we expect to have the policy tree created just once.
    ] + policy_members_to_list(policy_members, policy_record)

    assert strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id), zone.root
    ) == sorted(expected, key=sort_key)


@pytest.mark.django_db
def test_policy_record_with_ips_0_weight(zone, boto_client):
    policy = G(m.Policy)
    regions = get_local_aws_regions()
    ip = create_ip_with_healthcheck()
    policy_members = [
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip, weight=10),
        G(m.PolicyMember, policy=policy, region=regions[1], ip=ip, weight=0),
    ]

    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='@')
    policy_record.apply_record()
    expected = [
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A'
        },  # this is a ordinary record. should be not modified.
        # we expect to have the tree without the ip that has weight 0.
    ] + policy_members_to_list(policy_members, policy_record)

    assert strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id), zone.root
    ) == sorted(expected, key=sort_key)


@pytest.mark.django_db
def test_policy_record_with_all_ips_0_weight(zone, boto_client):
    policy = G(m.Policy)
    regions = get_local_aws_regions()
    ip = create_ip_with_healthcheck()

    G(m.PolicyMember, policy=policy, region=regions[0], ip=ip, weight=0),
    G(m.PolicyMember, policy=policy, region=regions[1], ip=ip, weight=0),

    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='@')
    policy_record.apply_record()
    expected = [
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A'
        },  # this is a ordinary record. should be not modified.
    ]

    rrsets = boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id)

    assert strip_ns_and_soa(rrsets, zone.root) == sorted(expected, key=sort_key)
