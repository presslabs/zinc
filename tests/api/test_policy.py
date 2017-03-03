# pylint: disable=no-member,protected-access,redefined-outer-name
import pytest
from django_dynamic_fixture import G

from tests.fixtures import api_client, boto_client, zone  # noqa: F401
from dns import models as m


def policy_member_to_dict(record):
    return {
        'id': str(record.id),
        'region': record.region,
        'ip': record.ip.ip,
        'weight': record.weight,
    }


def policy_to_dict(policy):
    return {
        'id': str(policy.id),
        'name': policy.name,
        'members': [policy_member_to_dict(member) for member in policy.members.all()],
        'url': 'http://testserver/policies/{}'.format(policy.id)
    }


@pytest.mark.django_db
def test_policy_list(api_client):
    pol = G(m.Policy)
    resp = api_client.get(
        '/policies',
        format='json',
    )
    assert resp.status_code == 200, resp
    assert [str(pol.id)] == [res['id'] for res in resp.data]


@pytest.mark.django_db
def test_policy_details(api_client):
    policy = G(m.Policy)
    response = api_client.get(
        '/policies/%s' % policy.id,
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
        '/policies/%s' % policy.id,
        format='json',
    )

    assert response.status_code == 200, response
    assert response.data == policy_to_dict(policy)
