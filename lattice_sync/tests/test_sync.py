import pytest
import responses

from dns.models import IP
from tests.fixtures import boto_client  # noqa: F401

from factories.dns.ip_factory import IPFactory
from lattice_sync import sync

lattice = sync.lattice_factory(url='http://lattice', user='user', password='password')


@pytest.mark.django_db
@responses.activate
def test_resets_existing_ips_on_run(boto_client):
    for url in ['http://lattice/servers/', 'http://lattice/datacenters/']:
        responses.add(responses.GET, url,
                      body='[]',
                      content_type='application/json')

    addr = '123.123.123.123'
    IPFactory(ip=addr)

    assert list(IP.objects.all().values_list('ip', flat=True)) == [addr]
    sync.sync(lattice)
    assert IP.objects.filter(ip=addr).count() == 0


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
    servers_payload = '''
    [{
    "hostname": "a.presslabs.net",
    "state": "configured",
    "group": "",
    "environment": "production",
    "roles": [
        "edge-node"
    ],
    "datacenter_name": "AMS1",
    "service_id": "",
    "ips": [{
        "ip": "123.123.123.123",
        "netmask": "",
        "gateway": "",
        "url": "http://localhost:8001/servers/a/ips/123.123.123.123?format=json",
        "description": ""},
        {
            "ip": "123.123.123.124",
            "netmask": "",
            "gateway": "",
            "url": "http://localhost:8001/servers/a/ips/123.123.123.124?format=json"
        }],
    "uplink_speed": null,
    "bandwidth": null,
    "memory": null,
    "cpu_model_name": "",
    "cpu_model_url": null,
    "datacenter_url": "http://localhost:8001/datacenters/5?format=json"},

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
        "description": ""}],
    "uplink_speed": null,
    "bandwidth": null,
    "memory": null,
    "cpu_model_name": "",
    "cpu_model_url": null,
    "datacenter_url": "http://localhost:8001/datacenters/6?format=json"}]'''

    datacenters_payload = '''[{
        "name": "AMS1",
        "location": "Amsterdam, NL",
        "provider": "providers.providers.DigitalOcean",
        "latitude": null,
        "longitude": null,
        "id": 5
    },
    {
        "name": "AMS2",
        "location": "Amsterdam, NL",
        "provider": "providers.providers.DigitalOcean",
        "latitude": null,
        "longitude": null,
        "id": 6
    }]'''

    responses.add(responses.GET, 'http://lattice/servers/',
                  body=servers_payload,
                  content_type='application/json')
    responses.add(responses.GET, 'http://lattice/datacenters/',
                  body=datacenters_payload,
                  content_type='application/json')
