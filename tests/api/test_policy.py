# pylint: disable=no-member,protected-access,redefined-outer-name
import pytest
from django_dynamic_fixture import G

from tests.fixtures import api_client, boto_client, zone
from dns import models as m


def policy_member_to_dict(member):
    return 'http://testserver/policy-members/{}/'.format(member.id)


def policy_to_dict(policy):
    return {
        'id': str(policy.id),
        'name': policy.name,
        'members': [policy_member_to_dict(member) for member in policy.members.all()],
        'url': 'http://testserver/policies/{}/'.format(policy.id)
    }


@pytest.mark.django_db
def test_policy_list(api_client):
    pol = G(m.Policy)
    resp = api_client.get(
        '/policies/',
        format='json',
    )
    assert resp.status_code == 200, resp
    assert [str(pol.id)] == [res['id'] for res in resp.data['results']]


@pytest.mark.django_db
def test_policy_create(api_client):
    resp = api_client.post(
        '/policies/',
        data={
            'name': 'spam',
        }
    )
    assert resp.status_code == 201, resp.data
    policy, = list(m.Policy.objects.all())
    assert resp.data == policy_to_dict(policy)


@pytest.mark.django_db
def test_policy_details(api_client):
    policy = G(m.Policy)
    response = api_client.get(
        '/policies/%s/' % policy.id,
        format='json',
    )
    assert response.status_code == 200, response
    assert response.data == policy_to_dict(policy)


@pytest.mark.django_db
def test_policy_with_records(api_client):
    policy = G(m.Policy)
    G(m.PolicyMember, policy=policy)
    G(m.PolicyMember, policy=policy)
    response = api_client.get(
        '/policies/%s/' % policy.id,
        format='json',
    )

    assert response.status_code == 200, response
    assert response.data == policy_to_dict(policy)


@pytest.mark.django_db
def test_policy_deletion(api_client):
    policy = G(m.Policy)
    G(m.PolicyMember, policy=policy)
    G(m.PolicyMember, policy=policy)
    assert m.PolicyMember.objects.count() == 2

    response = api_client.delete(
        '/policies/%s/' % policy.id,
        format='json',
    )

    assert response.status_code == 200, response
    assert m.PolicyMember.objects.count() == 0
    assert m.Policy.objects.count() == 0


def record_to_dict(record):
    return {
        'id': str(record.id),
        'location': record.location,
        'ip': record.ip.ip,
        'weight': record.weight,
    }


@pytest.mark.django_db
def test_policy_member(api_client):
    member = G(m.PolicyMember)
    response = api_client.get(
        '/policy-members/%s/' % member.id,
    )

    assert response.status_code == 200, response
    assert response.data == record_to_dict(member)
