# pylint: disable=no-member,protected-access,redefined-outer-name
import pytest
from django_dynamic_fixture import G

from tests.fixtures import boto_client, zone
from dns import models as m


@pytest.mark.django_db
def test_policy_record(zone):
    zone, client = zone
    policy = G(m.Policy)
    policy_record = G(m.PolicyRecord, zone=zone, policy=policy)

    policy_record.apply_record()
