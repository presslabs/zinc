# pylint: disable=no-member,protected-access,redefined-outer-name
import pytest
import botocore.exceptions

from zinc import models as m
from tests.fixtures import boto_client  # noqa: F401, pylint: disable=unused-import


@pytest.mark.django_db
def test_health_check_create(boto_client):
    ip = m.IP.objects.create(
        ip='1.2.3.4',
        hostname='fe01-mordor.presslabs.net.',
    )
    ip.reconcile_healthcheck()
    ip.refresh_from_db()
    expected_config = {
        'IPAddress': ip.ip,
        'Port': 80,
        'Type': 'HTTP',
        'ResourcePath': '/status',
        'FullyQualifiedDomainName': 'node.presslabs.net.',
    }
    resp = boto_client.get_health_check(HealthCheckId=ip.healthcheck_id)['HealthCheck']

    # {1:1, 2:2}.items() >= {2:2}.items() is True # first is a superset of the second, all is good
    # {1:1, 2:2}.items() <= {2:2}.items() is False # first is not a superset of the second
    assert resp['HealthCheckConfig'].items() >= expected_config.items()


@pytest.mark.django_db
def test_health_check_change(boto_client):
    ip = m.IP.objects.create(
        ip='1.2.3.4',
        hostname='fe01-mordor.presslabs.net.',
    )
    ip.reconcile_healthcheck()
    ip.refresh_from_db()
    original_check_id = ip.healthcheck_id
    expected_config = {
        'IPAddress': ip.ip,
        'Port': 80,
        'Type': 'HTTP',
        'ResourcePath': '/status',
        'FullyQualifiedDomainName': 'node.presslabs.net.',
    }
    resp = boto_client.get_health_check(HealthCheckId=ip.healthcheck_id)['HealthCheck']
    assert resp['HealthCheckConfig'].items() >= expected_config.items()

    ip.ip = '1.1.1.1'  # change the ip
    ip.save()
    ip.reconcile_healthcheck()
    ip.refresh_from_db()

    expected_config['IPAddress'] = ip.ip
    resp = boto_client.get_health_check(HealthCheckId=ip.healthcheck_id)['HealthCheck']
    assert resp['HealthCheckConfig'].items() >= expected_config.items()
    # ensure the old healthcheck got deleted
    with pytest.raises(botocore.exceptions.ClientError) as excp_info:
        boto_client.get_health_check(HealthCheckId=original_check_id)
    assert excp_info.value.response['Error']['Code'] == 'NoSuchHealthCheck'


@pytest.mark.django_db
def test_health_check_reconcile(boto_client):
    ip = m.IP.objects.create(
        ip='1.2.3.4',
        hostname='fe01-mordor.presslabs.net.',
    )
    ip.reconcile_healthcheck()
    ip.refresh_from_db()
    original_check_id = ip.healthcheck_id

    expected_config = {
        'IPAddress': ip.ip,
        'Port': 80,
        'Type': 'HTTP',
        'ResourcePath': '/status',
        'FullyQualifiedDomainName': 'node.presslabs.net.',
    }
    resp = boto_client.get_health_check(HealthCheckId=ip.healthcheck_id)['HealthCheck']
    assert resp['HealthCheckConfig'].items() >= expected_config.items()

    # simulate a failure during creation, so we have a HC in AWS but no HC id locally
    ip.healthcheck_id = None
    ip.save()
    # reconcile should preserve the caller reference and end up with the original id
    ip.reconcile_healthcheck()
    ip.refresh_from_db()
    assert ip.healthcheck_id == original_check_id
    resp = boto_client.get_health_check(HealthCheckId=ip.healthcheck_id)['HealthCheck']
    assert resp['HealthCheckConfig'].items() >= expected_config.items()
