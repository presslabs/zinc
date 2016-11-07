import responses

from mock import MagicMock, call

from django.core.management import call_command
from django.test import TestCase

from dns.models.ip import IP
from factories.dns.ip_factory import IPFactory
from dns.management.commands.ips_from_lattice import Command


class TestCommand(TestCase):
    def test_command_arguments(self):
        parser = MagicMock()
        command = Command()

        command.add_arguments(parser)

        parser.add_argument.assert_has_calls([
            call('--url', default=''),
            call('--user', default=''),
            call('--password', default=''),
            call('--roles', nargs='*')
        ], any_order=True)

    @responses.activate
    def test_resets_existing_ips_on_run(self):
        for url in ['http://lattice/servers/', 'http://lattice/datacenters/']:
            responses.add(responses.GET, url,
                          body='[]',
                          content_type='application/json')

        IPFactory(ip='123.123.123.123')

        self.assertEqual(IP.objects.exists(), True)

        args = []
        opts = {
            'url': 'http://lattice',
            'user': 'user',
            'password': 'password',
            'roles': ['frontend-node', 'cdn-node']
        }
        call_command('ips_from_lattice', *args, **opts)

        self.assertEqual(IP.objects.exists(), False)

    @responses.activate
    def test_adds_only_ips_from_servers_in_specified_roles(self):
        _mock_lattice_responses()

        args = []
        opts = {
            'url': 'http://lattice',
            'user': 'user',
            'password': 'password',
            'roles': ['frontend-node', 'cdn-node']
        }
        call_command('ips_from_lattice', *args, **opts)

        self.assertEqual(IP.objects.count(), 2)
        self.assertEqual(IP.objects.filter(ip__in=['123.123.123.123',
                                                   '123.123.123.124']).count(),
                         2)

    @responses.activate
    def test_fields_on_written_ip(self):
        _mock_lattice_responses()

        args = []
        opts = {
            'url': 'http://lattice',
            'user': 'user',
            'password': 'password',
            'roles': ['random-node']
        }
        call_command('ips_from_lattice', *args, **opts)

        ip = IP.objects.get(ip='123.123.123.125')

        expected_fields = {
            'ip': '123.123.123.125',
            'friendly_name': 'b AMS2 Amsterdam, NL',
            'enabled': True,
            'hostname': 'b'
        }
        for field, value in expected_fields.items():
            self.assertEqual(getattr(ip, field), value)


def _mock_lattice_responses():
    servers_payload = '''
    [{
    "hostname": "a",
    "state": "configured",
    "group": "",
    "environment": "production",
    "roles": [
        "frontend-node"
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
