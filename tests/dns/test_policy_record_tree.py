# pylint: disable=no-member,protected-access,redefined-outer-name
import pytest
from django_dynamic_fixture import G
from mock import patch, call

from tests.fixtures import boto_client, zone  # noqa: F401
from tests.utils import create_ip_with_healthcheck
from zinc import models as m

from zinc import route53


regions = route53.get_local_aws_regions()


def sort_key(record):
    return (record['Name'], record['Type'], record.get('SetIdentifier', None))


def strip_ns_and_soa(records, zone_root):
    """The NS and SOA records are managed by AWS, so we won't care about them in tests"""
    return sorted([
        record for record in records['ResourceRecordSets']
        if not(record['Type'] == 'SOA' or (record['Type'] == 'NS' and record['Name'] == zone_root))
    ], key=sort_key)


def policy_members_to_list(policy_members, policy_record, just_pr=False, no_health=False):
    """
    Tries to reproduce what should be in AWS after a policy is applied.
    """
    zone = policy_record.zone
    policy = policy_record.policy
    policy_members = [pm for pm in policy_members if pm.policy == policy]
    regions = set([pm.region for pm in policy_members])
    if len(regions) > 1:
        records_for_regions = [
            {
                'Name': '{}_{}.test-zinc.net.'.format(m.RECORD_PREFIX, policy.name),
                'Type': 'A',
                'AliasTarget': {
                    'DNSName': '{}_{}_{}.test-zinc.net.'.format(
                        m.RECORD_PREFIX, policy.name, region),
                    'EvaluateTargetHealth': len(regions) > 1,
                    'HostedZoneId': zone.route53_zone.id
                },
                'Region': region,
                'SetIdentifier': region,
            }
            for region in regions]
        records_for_policy_members = [
            {
                'Name': '{}_{}_{}.test-zinc.net.'.format(
                    m.RECORD_PREFIX, policy.name, policy_member.region),
                'Type': 'A',
                'ResourceRecords': [{'Value': policy_member.ip.ip}],
                'TTL': 30,
                'SetIdentifier': '{}-{}'.format(str(policy_member.id), policy_member.region),
                'Weight': policy_member.weight,
                'HealthCheckId': str(policy_member.ip.healthcheck_id),
            }
            for policy_member in policy_members if policy_member.enabled]

    else:
        records_for_regions = []
        records_for_policy_members = [
            {
                'Name': '{}_{}.test-zinc.net.'.format(m.RECORD_PREFIX, policy.name),
                'Type': 'A',
                'ResourceRecords': [{'Value': policy_member.ip.ip}],
                'TTL': 30,
                'SetIdentifier': '{}-{}'.format(str(policy_member.id), policy_member.region),
                'Weight': policy_member.weight,
                'HealthCheckId': str(policy_member.ip.healthcheck_id),
            }
            for policy_member in policy_members if policy_member.enabled]

    if no_health:
        for record in records_for_policy_members:
            del record['HealthCheckId']

    the_policy_record = []
    if len(regions) >= 1 or just_pr:
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
        ]
    return records_for_regions + records_for_policy_members + the_policy_record


@pytest.mark.django_db
def test_policy_member_to_list_helper():
    zone = G(m.Zone, route53_id='Fake')
    policy = G(m.Policy)
    region = regions[0]
    policy_members = [
        G(m.PolicyMember, policy=policy, region=region),
    ]
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy)
    result = policy_members_to_list(policy_members, policy_record)
    assert sorted(result, key=sort_key) == sorted([
        {
            'Name': '_zn_%s.test-zinc.net.' % (policy.name),
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
    ], key=sort_key)


@pytest.mark.django_db
def test_policy_member_to_list_helper_two_regions():
    zone = G(m.Zone, route53_id='Fake')
    policy = G(m.Policy)
    region = regions[0]
    region2 = regions[1]
    policy_members = [
        G(m.PolicyMember, policy=policy, region=region),
        G(m.PolicyMember, policy=policy, region=region2),
    ]
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy)
    result = policy_members_to_list(policy_members, policy_record)
    assert sorted(result, key=sort_key) == sorted([
        {
            'AliasTarget': {
                'DNSName': '_zn_%s_%s.test-zinc.net.' % (policy.name, region2),
                'EvaluateTargetHealth': True,
                'HostedZoneId': zone.route53_id
            },
            'Name': '_zn_%s.test-zinc.net.' % policy.name,
            'Region': region2,
            'SetIdentifier': region2,
            'Type': 'A'
        },
        {
            'AliasTarget': {
                'DNSName': '_zn_%s_%s.test-zinc.net.' % (policy.name, region),
                'EvaluateTargetHealth': True,
                'HostedZoneId': zone.route53_id
            },
            'Name': '_zn_%s.test-zinc.net.' % policy.name,
            'Region': region,
            'SetIdentifier': region,
            'Type': 'A'
        },
        {
            'Name': '_zn_%s_%s.test-zinc.net.' % (policy.name, region),
            'ResourceRecords': [{'Value': policy_members[0].ip.ip}],
            'SetIdentifier': '%s-%s' % (policy_members[0].id, region),
            'TTL': 30,
            'Type': 'A',
            'Weight': 10,
            'HealthCheckId': str(policy_members[0].ip.healthcheck_id),
        },
        {
            'Name': '_zn_%s_%s.test-zinc.net.' % (policy.name, region2),
            'ResourceRecords': [{'Value': policy_members[1].ip.ip}],
            'SetIdentifier': '%s-%s' % (policy_members[1].id, region2),
            'TTL': 30,
            'Type': 'A',
            'Weight': 10,
            'HealthCheckId': str(policy_members[1].ip.healthcheck_id),
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
    ], key=sort_key)


@pytest.mark.django_db
def test_policy_record_tree_builder(zone, boto_client):
    policy = G(m.Policy)
    region = regions[0]
    region2 = regions[1]
    ip = create_ip_with_healthcheck()
    policy_members = [
        G(m.PolicyMember, policy=policy, region=region, ip=ip),
        G(m.PolicyMember, policy=policy, region=region2, ip=ip),
    ]
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy)

    route53.Policy(policy=policy, zone=zone.route53_zone).reconcile()
    policy_record.r53_policy_record.reconcile()

    expected = [
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A',
        },
    ] + policy_members_to_list(policy_members, policy_record)
    expected = sorted(expected, key=sort_key)
    result = strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id), zone.root
    )
    assert result == expected


@pytest.mark.django_db
def test_policy_record_tree_with_multiple_regions(zone, boto_client):
    policy = G(m.Policy)
    ip = create_ip_with_healthcheck()
    policy_members = [
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip),
        G(m.PolicyMember, policy=policy, region=regions[1], ip=ip),
    ]
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy)

    zone.reconcile()

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

    zone.reconcile()

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
    # TODO: document the intention of this test
    policy = G(m.Policy)
    G(m.PolicyRecord, zone=zone, policy=policy)

    with pytest.raises(Exception) as exc:
        zone.reconcile()

    assert "Policy can't be applied" in str(exc)
    expected = [
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A'
        },
    ]

    assert strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id), zone.root
    ) == sorted(expected, key=sort_key)


@pytest.mark.django_db
def test_policy_record_tree_with_two_trees(zone, boto_client):
    policy = G(m.Policy)
    ip = create_ip_with_healthcheck()
    ip2 = create_ip_with_healthcheck()
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

    zone.reconcile()

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
    region = regions[0]
    ip = create_ip_with_healthcheck()
    policy_members = [
        G(m.PolicyMember, policy=policy, region=region, ip=ip),
        G(m.PolicyMember, policy=policy, region=region, ip=ip),
    ]
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy)

    zone.reconcile()

    expected = sorted(
        ([{
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A'
        }] + policy_members_to_list(policy_members, policy_record)),
        key=sort_key,
    )
    assert strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id), zone.root
    ) == expected

    policy_record.soft_delete()
    zone.reconcile()

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
    ip = create_ip_with_healthcheck()
    ip2 = create_ip_with_healthcheck()
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

    zone.reconcile()

    policy_record_to_delete.soft_delete()
    zone.reconcile()
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
    ip = create_ip_with_healthcheck()
    policy_members = [
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip, weight=10, enabled=True),
        G(m.PolicyMember, policy=policy, region=regions[1], ip=ip, weight=0, enabled=True),
    ]

    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='@')
    zone.reconcile()
    expected = [
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A'
        },  # this is a ordinary record. should be not modified.
        # we expect to have the tree without the ip that has weight 0.
    ] + policy_members_to_list(policy_members, policy_record)
    expected = sorted(expected, key=sort_key)
    actual = strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id), zone.root)
    assert actual == expected


@pytest.mark.django_db
def test_policy_record_with_all_ips_disabled(zone, boto_client):
    policy = G(m.Policy)
    ip1 = create_ip_with_healthcheck()
    ip1.enabled = False
    ip1.save()
    ip2 = create_ip_with_healthcheck()
    ip2.enabled = False
    ip2.save()

    G(m.PolicyMember, policy=policy, region=regions[0], ip=ip1)
    G(m.PolicyMember, policy=policy, region=regions[1], ip=ip2)

    G(m.PolicyRecord, zone=zone, policy=policy, name='@')

    with pytest.raises(Exception) as exc:
        zone.reconcile()
    assert "Policy can't be applied" in str(exc)
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


@pytest.mark.django_db
def test_apply_policy_on_zone(zone, boto_client):
    policy = G(m.Policy)
    ip = create_ip_with_healthcheck()

    policy_members = [
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip),
        G(m.PolicyMember, policy=policy, region=regions[1], ip=ip),
    ]
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='@')
    policy_record_2 = G(m.PolicyRecord, zone=zone, policy=policy, name='www')

    zone.reconcile()

    expected = [
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A'
        },  # this is a ordinary record. should be not modified.
    ] + (policy_members_to_list(policy_members, policy_record) +
         policy_members_to_list([], policy_record_2, just_pr=True))

    rrsets = boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id)
    assert strip_ns_and_soa(rrsets, zone.root) == sorted(expected, key=sort_key)


@pytest.mark.xfail
@pytest.mark.django_db
def test_apply_policy_is_not_duplicated(zone):
    policy = G(m.Policy)

    G(m.PolicyMember, policy=policy, region=regions[0])
    G(m.PolicyMember, policy=policy, region=regions[1])

    G(m.PolicyRecord, zone=zone, policy=policy, name='@')
    G(m.PolicyRecord, zone=zone, policy=policy, name='www')

    with patch('zinc.models.Policy.apply_policy') as apply_policy:
        with patch('zinc.models.PolicyRecord.apply_record'):
            zone.reconcile()
            apply_policy.assert_called_once_with(zone)


@pytest.mark.xfail
@pytest.mark.django_db
def test_apply_policy_ensure_both_policies_are_applied(zone):
    policy = G(m.Policy)
    policy_2 = G(m.Policy)

    G(m.PolicyMember, policy=policy, region=regions[0])
    G(m.PolicyMember, policy=policy_2, region=regions[1])

    G(m.PolicyRecord, zone=zone, policy=policy, name='@')
    G(m.PolicyRecord, zone=zone, policy=policy_2, name='www')

    with patch('zinc.models.Policy.apply_policy') as apply_policy:
        with patch('zinc.models.PolicyRecord.apply_record'):
            zone.reconcile()
            # assert called 2 times, because 2 policies.
            calls = [call(zone), call(zone)]
            apply_policy.assert_has_calls(calls)


@pytest.mark.django_db
def test_modifying_a_policy_member_in_policy_all_policy_members_get_dirty(zone):
    policy = G(m.Policy)
    ip = create_ip_with_healthcheck()

    G(m.PolicyMember, policy=policy, region=regions[0], ip=ip)
    policy_member = G(m.PolicyMember, policy=policy, region=regions[1], ip=ip)

    policy_records = [
        G(m.PolicyRecord, zone=zone, policy=policy, name='@'),
        G(m.PolicyRecord, zone=zone, policy=policy, name='www')
    ]

    zone.reconcile()
    policy_records_from_db = set(m.PolicyRecord.objects.all().values_list('id', 'dirty'))
    assert policy_records_from_db == set([(record.id, False) for record in policy_records])

    policy_member.weight = 3
    policy_member.save()

    policy_records_from_db = set(m.PolicyRecord.objects.all().values_list('id', 'dirty'))
    assert policy_records_from_db == set([(record.id, True) for record in policy_records])


@pytest.mark.django_db
def test_changing_an_disabled(zone):
    policy = G(m.Policy)

    ip = G(m.IP, healthcheck_id=None)
    ip2 = G(m.IP, healthcheck_id=None)

    G(m.PolicyMember, policy=policy, region=regions[0], ip=ip)
    G(m.PolicyMember, policy=policy, region=regions[1], ip=ip2)

    policy_records = [
        G(m.PolicyRecord, zone=zone, policy=policy, name='@', dirty=False),
        G(m.PolicyRecord, zone=zone, policy=policy, name='www', dirty=False)
    ]
    zone.reconcile()
    policy_records_from_db = set(m.PolicyRecord.objects.all().values_list('id', 'dirty'))
    assert policy_records_from_db == set([(record.id, False) for record in policy_records])


@pytest.mark.django_db
def test_ip_mark_policy_records_dirty(zone):
    policy1 = G(m.Policy)
    policy2 = G(m.Policy)

    ip1 = create_ip_with_healthcheck()
    ip2 = create_ip_with_healthcheck()

    G(m.PolicyMember, policy=policy1, region=regions[0], ip=ip1)
    G(m.PolicyMember, policy=policy2, region=regions[1], ip=ip2)

    policy_record_1 = G(m.PolicyRecord, zone=zone, policy=policy1, name='pr1', dirty=False)
    policy_record_2 = G(m.PolicyRecord, zone=zone, policy=policy1, name='pr2', dirty=False)
    other_zone_policy_record = G(
        m.PolicyRecord, zone=zone, policy=policy2, name='oz_pr', dirty=False)

    ip1.mark_policy_records_dirty()

    policy_record_1.refresh_from_db()
    policy_record_2.refresh_from_db()
    other_zone_policy_record.refresh_from_db()

    assert policy_record_1.dirty is True
    assert policy_record_2.dirty is True
    assert other_zone_policy_record.dirty is False  # different policy, should not have changed


@pytest.mark.django_db
def test_tree_with_one_region(zone, boto_client):
    policy = G(m.Policy)
    ip = G(m.IP, healthcheck_id=None)
    ip2 = G(m.IP, healthcheck_id=None)

    policy_members = [
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip),
        G(m.PolicyMember, policy=policy, region=regions[0], ip=ip2)
    ]

    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='@')

    zone.reconcile()

    expected = [
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A'
        },  # this is a ordinary record. should be not modified.
    ] + policy_members_to_list(policy_members, policy_record, no_health=True)

    rrsets = boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id)
    assert strip_ns_and_soa(rrsets, zone.root) == sorted(expected, key=sort_key)


@pytest.mark.django_db
def test_dangling_records(zone, boto_client):
    """
    Tests a dangling record in an existing policy tree gets removed.
    """
    dangling_record = {
        'Name': '_zn_test1.us-east-1.' + zone.root,
        'Type': 'A',
        'ResourceRecords': [{'Value': '127.1.1.1'}],
        'SetIdentifier': 'test-identifier',
        'Weight': 20,
        'TTL': 30
    }

    boto_client.change_resource_record_sets(
        HostedZoneId=zone.route53_id,
        ChangeBatch={
            'Comment': 'string',
            'Changes': [
                {
                    'Action': 'CREATE',
                    'ResourceRecordSet': dangling_record
                }
            ]
        }
    )

    ip = create_ip_with_healthcheck()
    policy = G(m.Policy, name='test1')
    G(m.PolicyMember, ip=ip, policy=policy, region='us-east-1', weight=10)
    G(m.PolicyRecord, zone=zone, policy=policy, name='record', dirty=False)
    route53.Policy(policy=policy, zone=zone.route53_zone).reconcile()

    records = boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id)
    assert dangling_record not in records['ResourceRecordSets']


@pytest.mark.django_db
def test_change_policy(zone, boto_client):
    """
    Tests that changing the policy for a policy_record doesn't leave dangling record behind
    """
    ip1 = create_ip_with_healthcheck()
    ip2 = create_ip_with_healthcheck()
    policy1 = G(m.Policy, name='policy1')
    policy2 = G(m.Policy, name='policy2')
    # add each IP to both policies
    G(m.PolicyMember, ip=ip1, policy=policy1, region='us-east-1', weight=10)
    G(m.PolicyMember, ip=ip1, policy=policy2, region='us-east-1', weight=10)
    G(m.PolicyMember, ip=ip2, policy=policy1, region='us-east-2', weight=10)
    G(m.PolicyMember, ip=ip2, policy=policy2, region='us-east-2', weight=10)
    # build a tree with policy1
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy1, name='record', dirty=True)
    zone.reconcile()
    # switch to policy2 and rebuild
    policy_record.policy = policy2
    policy_record.dirty = True
    policy_record.save()
    zone.reconcile()

    records = boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id)
    policy1_records = [record['Name'] for record in records['ResourceRecordSets']
                       if record['Name'].startswith('_zn_policy1')]
    assert policy1_records == []


@pytest.mark.django_db
def test_untouched_policy_not_deleted(zone, boto_client):
    """
    Tests a policy record with dirty=False doesn't end up deleted after a tree rebuild.
    """
    ip1 = create_ip_with_healthcheck()
    policy1 = G(m.Policy, name='policy1')
    G(m.PolicyMember, ip=ip1, policy=policy1, region='us-east-1', weight=10)

    ip2 = create_ip_with_healthcheck()
    policy2 = G(m.Policy, name='policy2')
    G(m.PolicyMember, ip=ip2, policy=policy2, region='us-east-2', weight=10)

    # build a tree with policy1
    G(m.PolicyRecord, zone=zone, policy=policy1, name='policy_record1', dirty=True)
    zone.reconcile()

    # add another policy record
    G(m.PolicyRecord, zone=zone, policy=policy2, name='policy_record2', dirty=True)
    zone.reconcile()

    records = boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id)
    policy_records = set([record['Name'] for record in records['ResourceRecordSets']
                          if record['Name'].startswith('_zn_')])

    # check policy1's records are still here
    assert policy_records == set(['_zn_policy1.test-zinc.net.', '_zn_policy2.test-zinc.net.'])


@pytest.mark.django_db
def test_delete_policy_record(zone, boto_client):
    """
    Tests a policy record by deleting and creating immediate after. Issue #210
    """
    ip1 = create_ip_with_healthcheck()
    policy = G(m.Policy, name='policy')
    G(m.PolicyMember, ip=ip1, policy=policy, region='us-east-1', weight=10)
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='www', dirty=True)

    zone.reconcile()  # reconcile
    policy_record.soft_delete()  # delete the record
    zone.reconcile()  # reconcile

    # assert the object is deleted.
    assert not m.PolicyRecord.objects.filter(id=policy_record.id).exists()

    # assert route53 should be empty
    expected = sorted([
        {
            'Name': 'test.test-zinc.net.',
            'ResourceRecords': [{'Value': '1.1.1.1'}],
            'TTL': 300,
            'Type': 'A'
        },  # this is a ordinary record. should be not modified.
    ], key=sort_key)
    result = strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.route53_id), zone.root
    )
    assert result == expected

@pytest.mark.django_db
def test_r53_policy_record_aws_records(zone, boto_client):
    """
    Tests a PolicyRecord loads it's records correctly from AWS
    """
    zone.add_record(route53.Record(
        name='_zn_pol1.us-east-1',
        values=['1.2.3.4'],
        type='A',
        zone=zone.route53_zone,
        ttl=30,
        set_identifier='foo',
        weight=10,
    ))
    zone.add_record(
        route53.Record(
            name='_zn_pol1',
            alias_target={
                'DNSName': '_zn_pol1.us-east-1.{}'.format(zone.root),
                'HostedZoneId': zone.route53_zone.id,
                'EvaluateTargetHealth': False
            },
            type='A',
            zone=zone.route53_zone,
        ))
    zone.commit()
    policy = G(m.Policy, name='pol1')
    policy_record = G(m.PolicyRecord, zone=zone, name='www', policy=policy)
    policy = route53.Policy(zone=zone.route53_zone, policy=policy_record.policy)
    assert set([r.name for r in policy.aws_records.values()]) == set([
        '_zn_pol1', '_zn_pol1.us-east-1'])


@pytest.mark.django_db
def test_r53_policy_record_expected_aws_records(zone, boto_client):
    """
    Tests a PolicyRecord loads it's records correctly from AWS
    """
    policy = G(m.Policy, name='pol1')
    policy_record = G(m.PolicyRecord, zone=zone, name='www', policy=policy)

    ip1 = create_ip_with_healthcheck()
    G(m.PolicyMember, policy=policy_record.policy, region=regions[0], ip=ip1)
    G(m.PolicyMember, policy=policy_record.policy, region=regions[1], ip=ip1)
    # pol_factory = route53.CachingFactory(route53.Policy)
    r53_policy = route53.Policy(zone=zone.route53_zone, policy=policy)
    assert [(r.name, r.values) for r in r53_policy.desired_records.values()] == [
        ('_zn_pol1_us-east-1', [ip1.ip]),
        ('_zn_pol1_us-east-2', [ip1.ip]),
        ('_zn_pol1', ['ALIAS _zn_pol1_us-east-1.test-zinc.net.']),
        ('_zn_pol1', ['ALIAS _zn_pol1_us-east-2.test-zinc.net.']),
    ]


@pytest.mark.django_db
def test_r53_policy_reconcile(zone, boto_client):
    policy = G(m.Policy, name='pol1')
    policy_record = G(m.PolicyRecord, zone=zone, name='www', policy=policy)

    ip1 = create_ip_with_healthcheck()
    G(m.PolicyMember, policy=policy_record.policy, region=regions[0], ip=ip1)
    G(m.PolicyMember, policy=policy_record.policy, region=regions[1], ip=ip1)
    # pol_factory = route53.CachingFactory(route53.Policy)
    r53_policy = route53.Policy(zone=zone.route53_zone, policy=policy)
    r53_policy.reconcile()

    raw_aws_records = [route53.Record.from_aws_record(r, zone=zone)
                       for r in strip_ns_and_soa(boto_client.list_resource_record_sets(
                               HostedZoneId=zone.route53_id), zone.root)]
    # only look at the hidden records (the ones part of the policy tree)
    records = [(r.name, r.values) for r in raw_aws_records if r.is_hidden]
    assert records == [
        ('_zn_pol1', ['ALIAS _zn_pol1_us-east-1.test-zinc.net.']),
        ('_zn_pol1', ['ALIAS _zn_pol1_us-east-2.test-zinc.net.']),
        ('_zn_pol1_us-east-1', [ip1.ip]),
        ('_zn_pol1_us-east-2', [ip1.ip]),
    ]
