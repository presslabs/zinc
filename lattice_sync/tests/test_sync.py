import json

import pytest
import responses
from django_dynamic_fixture import G

from lattice_sync import sync
from tests.fixtures import boto_client  # noqa: F401
from zinc.models import IP

lattice = sync.lattice_factory(url='http://lattice', user='user', password='password')


@pytest.mark.django_db
@responses.activate
def test_wont_delete_all_ips(boto_client):
    for url in ['http://lattice/servers', 'http://lattice/datacenters']:
        responses.add(responses.GET, url,
                      body='[]',
                      content_type='application/json')

    addr = '123.123.123.123'
    G(IP, ip=addr)

    assert list(IP.objects.all().values_list('ip', flat=True)) == [addr]
    with pytest.raises(AssertionError) as excp_info:
        sync.sync(lattice)
    assert excp_info.match("Refusing to delete all IPs")
    assert list(IP.objects.values_list('ip', flat=True)) == [addr]


@pytest.mark.django_db
@responses.activate
def test_removes_ip(boto_client):
    _mock_lattice_responses()

    addr = '1.2.3.4'  # not in the mock response
    G(IP, ip='1.2.3.4')

    assert list(IP.objects.all().values_list('ip', flat=True)) == [addr]
    sync.sync(lattice)
    assert not IP.objects.filter(ip=addr).exists()


@pytest.mark.django_db
@responses.activate
def test_adds_only_ips_from_servers_in_specified_roles(boto_client):
    _mock_lattice_responses()

    sync.sync(lattice)

    assert IP.objects.count() == 2
    assert IP.objects.filter(ip__in=['123.123.123.123', '123.123.123.124']).count() == 2


@pytest.mark.django_db
@responses.activate
def test_fields_on_written_ip(boto_client):
    _mock_lattice_responses()

    sync.sync(lattice)

    ip = IP.objects.get(ip='123.123.123.123')

    expected_fields = {
        'ip': '123.123.123.123',
        'friendly_name': 'a Amsterdam, NL',
        'enabled': True,
        'hostname': 'a.presslabs.net'
    }
    attributes = {
        field: getattr(ip, field)
        for field in expected_fields.keys()
    }
    assert attributes == expected_fields


def _mock_lattice_responses():
    servers_payload = [
        {
            "hostname": "a.presslabs.net",
            "state": "configured",
            "group": "",
            "environment": "production",
            "roles": [
                "edge-node"
            ],
            "datacenter_name": "AMS1",
            "service_id": "",
            "ips": [
                {
                    "ip": "123.123.123.123",
                    "netmask": "",
                    "gateway": "",
                    "url": "http://localhost:8001/servers/a/ips/123.123.123.123?format=json",
                    "description": ""
                },
                {
                    "ip": "123.123.123.124",
                    "netmask": "",
                    "gateway": "",
                    "url": "http://localhost:8001/servers/a/ips/123.123.123.124?format=json"
                }],
            "uplink_speed": None,
            "bandwidth": None,
            "memory": None,
            "cpu_model_name": "",
            "cpu_model_url": None,
            "datacenter_url": "http://localhost:8001/datacenters/5?format=json"
        },
        {
            "hostname": "b",
            "state": "configured",
            "group": "",
            "environment": "production",
            "roles": [
                "random-node"
            ],
            "datacenter_name": "AMS2",
            "service_id": "",
            "ips": [{
                "ip": "123.123.123.125",
                "netmask": "",
                "gateway": "",
                "url": "http://localhost:8001/servers/b/ips/123.123.123.125?format=json",
                "description": ""
            }],
            "uplink_speed": None,
            "bandwidth": None,
            "memory": None,
            "cpu_model_name": "",
            "cpu_model_url": None,
            "datacenter_url": "http://localhost:8001/datacenters/6?format=json"
        }]

    datacenters_payload = [
        {
            "name": "AMS1",
            "location": "Amsterdam, NL",
            "provider": "providers.providers.DigitalOcean",
            "latitude": None,
            "longitude": None,
            "id": 5
        },
        {
            "name": "AMS2",
            "location": "Amsterdam, NL",
            "provider": "providers.providers.DigitalOcean",
            "latitude": None,
            "longitude": None,
            "id": 6
        }]

    responses.add(responses.GET, 'http://lattice/servers',
                  body=json.dumps(servers_payload),
                  content_type='application/json')
    responses.add(responses.GET, 'http://lattice/datacenters',
                  body=json.dumps(datacenters_payload),
                  content_type='application/json')
