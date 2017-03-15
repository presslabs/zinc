import json
from unittest import mock

import pytest

from zinc import ns_check, models
from tests.fixtures import zone, boto_client, Moto  # noqa: F401


@pytest.mark.parametrize("boto_client", [Moto], ids=['fake_boto'], indirect=True)
@pytest.mark.django_db
def test_is_ns_propagated(zone, boto_client):
    resolver = mock.Mock()
    resolver.query.return_value = ["test_ns1.presslabs.net", "test_ns2.presslabs.net"]
    with mock.patch('zinc.ns_check.get_resolver', lambda: resolver):
        assert ns_check.is_ns_propagated(zone)


@pytest.mark.parametrize("boto_client", [Moto], ids=['fake_boto'], indirect=True)
@pytest.mark.django_db
def test_is_ns_propagated_delegated_zone(zone, boto_client):
    """Ensure is_ns_propagated ignores NS records for delegated zones
    The root cause of https://github.com/PressLabs/zinc/issues/182
    """
    boto_client.change_resource_record_sets(
        HostedZoneId=zone.route53_id,
        ChangeBatch={
            'Comment': 'zinc-fixture',
            'Changes': [
                {
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'Name': 'delegated.' + zone.root,
                        'Type': 'NS',
                        'TTL': 300,
                        'ResourceRecords': [
                            {
                                'Value': 'ns1.example.com',
                            }
                        ]
                    }
                },
            ]
        }
    )
    resolver = mock.Mock()
    resolver.query.return_value = ["test_ns1.presslabs.net", "test_ns2.presslabs.net"]
    with mock.patch('zinc.ns_check.get_resolver', lambda: resolver):
        assert ns_check.is_ns_propagated(zone)


@pytest.mark.parametrize("boto_client", [Moto], ids=['fake_boto'], indirect=True)
@pytest.mark.django_db
def test_is_ns_propagated_false(zone):
    resolver = mock.Mock()
    resolver.query.return_value = ["some_other_ns.example.com"]
    with mock.patch('zinc.ns_check.get_resolver', lambda: resolver):
        assert ns_check.is_ns_propagated(zone) is False


@pytest.mark.parametrize("boto_client", [Moto], ids=['fake_boto'], indirect=True)
@pytest.mark.django_db
def test_update_ns_propagated(zone):
    assert zone.ns_propagated is False
    resolver = mock.Mock()
    resolver.query.return_value = ["test_ns1.presslabs.net", "test_ns2.presslabs.net"]
    with mock.patch('zinc.ns_check.get_resolver', lambda: resolver):
        models.Zone.update_ns_propagated()
    zone.refresh_from_db()
    assert zone.ns_propagated


@pytest.mark.parametrize("boto_client", [Moto], ids=['fake_boto'], indirect=True)
@pytest.mark.django_db
def test_update_ns_propagated_false(zone):
    assert zone.ns_propagated is False
    resolver = mock.Mock()
    resolver.query.return_value = ["some_other_ns.example.com"]
    with mock.patch('zinc.ns_check.get_resolver', lambda: resolver):
        models.Zone.update_ns_propagated()
    zone.refresh_from_db()
    assert zone.ns_propagated is False


@pytest.mark.parametrize("boto_client", [Moto], ids=['fake_boto'], indirect=True)
@pytest.mark.django_db
def test_update_ns_propagated_updates_cached_ns_records_empty_cache(zone):
    assert zone.cached_ns_records is None
    ns_records = ["test_ns1.presslabs.net", "test_ns2.presslabs.net"]
    resolver = mock.Mock()
    resolver.query.return_value = ["test_ns1.presslabs.net", "test_ns2.presslabs.net"]
    with mock.patch('zinc.ns_check.get_resolver', lambda: resolver):
        models.Zone.update_ns_propagated()
    zone.refresh_from_db()
    assert set(json.loads(zone.cached_ns_records)) == set(ns_records)
    assert zone.ns_propagated


@pytest.mark.parametrize("boto_client", [Moto], ids=['fake_boto'], indirect=True)
@pytest.mark.django_db
def test_update_ns_propagated_updates_cached_ns_records(zone):
    zone.cached_ns_records = json.dumps(["ns1.example.com"])
    zone.save()
    ns_records = ["test_ns1.presslabs.net", "test_ns2.presslabs.net"]
    resolver = mock.Mock()
    resolver.query.return_value = ["test_ns1.presslabs.net", "test_ns2.presslabs.net"]
    with mock.patch('zinc.ns_check.get_resolver', lambda: resolver):
        models.Zone.update_ns_propagated()
    zone.refresh_from_db()
    assert set(json.loads(zone.cached_ns_records)) == set(ns_records)
    assert zone.ns_propagated
