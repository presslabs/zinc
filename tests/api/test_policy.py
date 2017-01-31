# pylint: disable=no-member,protected-access,redefined-outer-name
import pytest
from django_dynamic_fixture import G

from tests.fixtures import api_client, boto_client, zone
from dns import models as m


def policy_to_dict(policy):
    assert policy.members.all().count() == 0
    return {
        'id': str(policy.id),
        'name': policy.name,
        'members': [],
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
