# pylint: disable=no-member,unused-argument,protected-access,redefined-outer-name
import pytest

from django_dynamic_fixture import G

from tests.fixtures import api_client, boto_client, zone  # noqa: F401
from tests.utils import (strip_ns_and_soa, hash_policy_record,
                         get_test_record, create_ip_with_healthcheck)
from zinc import models as m
from zinc.route53 import get_local_aws_regions
from zinc import route53


regions = get_local_aws_regions()


def get_policy_record(policy_record, dirty=False, managed=False):
    return {
        'id': hash_policy_record(policy_record),
        'name': policy_record.name,
        'fqdn': ('{}.{}'.format(policy_record.name, policy_record.zone.root)
                 if policy_record.name != '@' else policy_record.zone.root),
        'type': 'POLICY_ROUTED_IPv6' if policy_record.record_type == 'AAAA' else 'POLICY_ROUTED',
        'values': [str(policy_record.policy.id)],
        'ttl': None,
        'dirty': dirty,
        'managed': managed,
        'url': 'http://testserver/zones/{}/records/{}'.format(
            policy_record.zone.id,
            hash_policy_record(policy_record))
    }


@pytest.mark.django_db
def test_policy_record_get(api_client, zone, boto_client):
    policy = G(m.Policy)
    ip = create_ip_with_healthcheck()
    ip2 = create_ip_with_healthcheck()
    G(m.PolicyMember, policy=policy, region=regions[0], ip=ip)
    G(m.PolicyMember, policy=policy, region=regions[0], ip=ip2)
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='@')
    zone.reconcile()

    response = api_client.get(
        '/zones/%s' % zone.id
    )

    response_data = strip_ns_and_soa(response.data['records'])
    expected = [
        get_test_record(zone),
        get_policy_record(policy_record),
    ]
    assert response_data == expected


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
    assert response.status_code == 201, response.data
    pr = m.PolicyRecord.objects.get(name='@', record_type='A', zone=zone)
    assert response.data == get_policy_record(pr, dirty=True)


@pytest.mark.django_db
def test_policy_record_create_ipv6(api_client, zone):
    policy = G(m.Policy)
    G(m.PolicyMember, policy=policy, region=regions[0])

    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data={
            'name': '@',
            'type': 'POLICY_ROUTED_IPv6',
            'values': [str(policy.id)],
        }
    )
    assert response.status_code == 201, response.data
    pr = m.PolicyRecord.objects.get(name='@', record_type='AAAA', zone=zone)
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
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy, name='@', dirty=True)
    policy_record_2 = G(m.PolicyRecord, zone=zone, policy=policy, name='www', dirty=True)
    zone.reconcile()

    response = api_client.get(
        '/zones/%s' % zone.id
    )

    result = strip_ns_and_soa(response.data['records'])
    expected = [
        get_test_record(zone),
        get_policy_record(policy_record),
        get_policy_record(policy_record_2),
    ]
    assert result == expected


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
    """Tests we can't create a PR when we have a CNAME with the same name"""
    boto_client.change_resource_record_sets(
        HostedZoneId=zone.r53_zone.id,
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


@pytest.mark.django_db
def test_delete_policy_record_with_cname_clash(zone, api_client, boto_client):
    """Tests we can delete a PR when we already have a CNAME with the same name

    The API guards against even getting this conflict but if you bypass, it like
    we did when we imported all our PolicyRecords, you still want to be able to
    delete it.
    """
    boto_client.change_resource_record_sets(
        HostedZoneId=zone.r53_zone.id,
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
    policy_record = G(m.PolicyRecord, name='www', policy=policy, zone=zone, dirty=False)
    # reconciling the zone would now fail because of the conflicting CNAME
    # also, the validation cares about the DB value of PolicyRecord, so it's not even required
    response = api_client.delete(
        '/zones/{}/records/{}'.format(zone.id, hash_policy_record(policy_record)))
    assert response.status_code == 204


@pytest.mark.django_db
def test_cname_create_with_pr_clash(zone, api_client):
    """Tests we can't create a CNAME when we have a PR with the same name"""
    policy = G(m.Policy)
    region = get_local_aws_regions()[0]
    ip = create_ip_with_healthcheck()
    G(m.PolicyMember, policy=policy, region=region, ip=ip)
    policy_record = route53.PolicyRecord(
        policy_record=m.PolicyRecord(policy=policy, zone=zone, name='conflict'),
        zone=zone.r53_zone,
    )
    policy_record.save()

    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data={
            'name': 'conflict',
            'type': 'CNAME',
            'values': 'conflict.example.net.'
        })
    assert response.data['name'] == ['A POLICY_ROUTED record of the same name already exists.']


@pytest.mark.django_db
def test_txt_create_with_A_clash(zone, api_client):
    """Tests we can create a TXT when we have an A record with the same name"""
    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data={
            'name': 'conflict',
            'type': 'A',
            'values': '1.2.3.4'
        })
    assert response.status_code == 201
    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data={
            'name': 'conflict',
            'type': 'TXT',
            'values': 'the rain in spain'
        })
    assert response.status_code == 201
    expected = [(r.name, r.type, r.values) for r in zone.r53_zone.records().values()
                if r.name == 'conflict']
    assert sorted(expected) == [
        ('conflict', 'A', ['1.2.3.4']),
        ('conflict', 'TXT', ['the rain in spain']),
    ]


@pytest.mark.django_db
def test_cname_patch(zone, api_client):
    """Tests we can patch a CNAME record"""
    cname = route53.Record(
        zone=zone.r53_zone,
        type='CNAME',
        name='cname',
        values=['ham.example.net.'],
        ttl=300,
    )
    cname.save()
    zone.commit()
    response = api_client.patch(
        '/zones/{}/records/{}'.format(zone.id, cname.id),
        data={
            'values': 'spam.exmaple.net.'
        })
    assert response.status_code == 200, response.data
    expected = [(r.name, r.type, r.values) for r in zone.r53_zone.records().values()
                if r.name == 'cname']
    assert sorted(expected) == [
        ('cname', 'CNAME', ['spam.exmaple.net.']),
    ]


@pytest.mark.django_db
def test_post_doesnt_overwite_existing(zone, api_client):
    """
    Tests posting a new record of the same name and type with different values fails.
    """
    record = route53.Record(
        zone=zone.r53_zone,
        type='A',
        name='conflict',
        values=['1.2.3.4'],
        ttl=30,
    )
    record.save()
    zone.commit()
    response = api_client.post(
        '/zones/{}/records'.format(zone.id),
        data={
            'type': 'A',
            'name': 'conflict',
            'values': '5.6.7.8'
        })
    expected = [(r.name, r.type, r.values) for r in zone.r53_zone.records().values()
                if r.name == 'conflict']
    assert sorted(expected) == [
        ('conflict', 'A', ['1.2.3.4']),
    ]
    response.status_code == 400, response.data


@pytest.mark.django_db
def test_delete_then_create_policy_record(zone, api_client):
    policy = G(m.Policy)
    ip = create_ip_with_healthcheck()
    G(m.PolicyMember, policy=policy, region=get_local_aws_regions()[0], ip=ip)

    policy_record = G(m.PolicyRecord, policy=policy, zone=zone, name='www')
    response = api_client.delete(
        '/zones/%s/records/%s' % (zone.id, hash_policy_record(policy_record))
    )

    assert response.status_code == 204
    pr = m.PolicyRecord.objects.get(id=policy_record.id)
    assert pr.dirty is True
    assert pr.deleted is True

    response = api_client.post(
        '/zones/%s/records' % (zone.id),
        data={
            'name': policy_record.name,  # same name
            'type': 'POLICY_ROUTED',
            'values': [str(policy.id)]
        }
    )  # this will be an update

    assert response.status_code == 201
    pr = m.PolicyRecord.objects.get(id=policy_record.id)
    assert pr.id == policy_record.id
    assert pr.dirty is True
    assert pr.deleted is False
