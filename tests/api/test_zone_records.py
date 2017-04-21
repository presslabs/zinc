# pylint: disable=no-member,unused-argument,protected-access,redefined-outer-name
import pytest
from unittest.mock import patch

from django_dynamic_fixture import G
from botocore.exceptions import ClientError

from tests.fixtures import api_client, boto_client, zone  # noqa: F401
from tests.utils import (strip_ns_and_soa, hash_test_record, aws_strip_ns_and_soa, aws_sort_key,
                         get_test_record, record_data_to_aws, get_record_from_base)
from zinc import models as m
from zinc import route53


@pytest.mark.django_db
def test_get_record(api_client, zone):
    G(m.Zone)

    response = api_client.get(
        '/zones/{}/records/{}'.format(zone.id, hash_test_record(zone))
    )

    assert response.data == get_test_record(zone)


@pytest.mark.django_db
def test_create_record(api_client, zone, boto_client):
    G(m.Zone)

    record = {
        'name': 'record1',
        'type': 'A',
        'ttl': 300,
        'values': ['1.2.3.4']
    }
    response = api_client.post(
        '/zones/{}/records'.format(zone.id),
        data=record
    )

    assert response.data == get_record_from_base(record, zone)
    assert aws_strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.r53_zone.id), zone.root
    ) == sorted([
        record_data_to_aws(record, zone.root),
        record_data_to_aws(get_test_record(zone), zone.root)
    ], key=aws_sort_key)


@pytest.mark.django_db
def test_update_record_values(api_client, zone, boto_client):
    G(m.Zone)

    record_data = {
        'values': ['1.2.3.4']
    }
    response = api_client.patch(
        '/zones/{}/records/{}'.format(zone.id, hash_test_record(zone)),
        data=record_data)

    assert response.data == {
        **get_test_record(zone),
        **record_data
    }
    assert aws_strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.r53_zone.id), zone.root
    ) == sorted([
        record_data_to_aws({
            **get_test_record(zone),
            **record_data
        }, zone.root)
    ], key=aws_sort_key)


@pytest.mark.django_db
def test_update_record_ttl(api_client, zone, boto_client):
    G(m.Zone)

    record_data = {
        'ttl': 580
    }
    response = api_client.patch(
        '/zones/{}/records/{}'.format(zone.id, hash_test_record(zone)),
        data=record_data
    )

    assert response.data == {
        **get_test_record(zone),
        **record_data
    }
    assert aws_strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.r53_zone.id), zone.root
    ) == sorted([
        record_data_to_aws({
            **get_test_record(zone),
            **record_data
        }, zone.root)
    ], key=aws_sort_key)


@pytest.mark.django_db
def test_update_record_type(api_client, zone):
    G(m.Zone)

    record = {
        'type': 'CNAME'
    }
    response = api_client.patch(
        '/zones/{}/records/{}'.format(zone.id, hash_test_record(zone)),
        data=record
    )
    assert response.data == {
        'non_field_errors': ["Can't update 'name' and 'type' fields. "]
    }


@pytest.mark.django_db
def test_hash_test_record(zone):
    assert hash_test_record(zone)[-16:] == 'Z1ZOrpXqQazJdzbN'


@pytest.mark.django_db
def test_update_record_name(api_client, zone):
    G(m.Zone)
    response = api_client.patch(
        '/zones/{}/records/{}'.format(zone.id, hash_test_record(zone)),
        data={
            'name': 'CNAME'
        }
    )
    assert response.data == {
        'non_field_errors': ["Can't update 'name' and 'type' fields. "]
    }


@pytest.mark.django_db
def test_record_deletion(api_client, zone, boto_client):
    record_hash = hash_test_record(zone)
    response = api_client.delete(
        '/zones/%s/records/%s' % (zone.id, record_hash),
    )
    assert response.status_code == 204
    assert strip_ns_and_soa(zone.records) == []
    assert aws_strip_ns_and_soa(
        boto_client.list_resource_record_sets(HostedZoneId=zone.r53_zone.id),
        zone.root
    ) == []


@pytest.mark.django_db
def test_delete_nonexistent_records(api_client, zone):
    record2 = route53.Record(
        name='detest',
        ttl=400,
        type='NS',
        values=['ns.test.com', 'ns2.test.com'],
        zone=zone.r53_zone,
    )
    zone.update_records([record2])
    zone.r53_zone.commit()
    response = api_client.delete(
        '/zones/%s/records/%s' % (zone.id, 'asldmpoqfqee')
    )
    assert response.status_code == 404
    assert response.data == {'detail': 'Record not found.'}


@pytest.mark.django_db
def test_patch_nonexistent_records(api_client, zone):
    response = api_client.patch(
        '/zones/%s/records/%s' % (zone.id, 'asldmpoqfqee')
    )
    assert response.status_code == 404
    assert response.data == {'detail': 'Record not found.'}


@pytest.mark.django_db
def test_add_record_without_values(api_client, zone):
    record = {
        'name': 'test1',
        'ttl': 400,
        'type': 'A',
    }
    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data=record
    )
    assert response.data == {'values': ['This field is required.']}


@pytest.mark.django_db
def test_add_record_without_ttl(api_client, zone):
    record = {
        'name': 'test1',
        'type': 'A',
        'values': ['4.5.6.7']
    }
    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data=record
    )
    assert response.data.get('ttl') == 300
    assert response.status_code == 201


@pytest.mark.django_db
def test_add_record_without_ttl_and_values(api_client, zone):
    record = {
        'name': 'test',
        'type': 'A',
    }
    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data=record
    )
    assert response.status_code == 400
    assert response.data == {
        'values': ['This field is required.']
    }


@pytest.mark.django_db
def test_add_record_invalid_ttl(api_client, zone):
    record = {
        'name': 'test',
        'type': 'A',
        'ttl': 0,
        'valuse': ['4.5.6.7'],
    }
    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data=record
    )
    assert response.data == {
        'ttl': ['Ensure this value is greater than or equal to 1.']
    }


@pytest.mark.django_db
def test_hidden_records(api_client, zone):
    """Tests any record starting with RECORD_PREFIX is hidden by the api"""
    route53.Record(
        name='{}_ceva'.format(m.RECORD_PREFIX),
        ttl=300,
        type='A',
        values=['1.2.3.4'],
        zone=zone.r53_zone,
    ).save()
    zone.r53_zone.commit()
    response = api_client.get(
        '/zones/%s' % zone.id,
    )
    assert strip_ns_and_soa(response.data['records']) == [
        get_test_record(zone)
    ]


@pytest.mark.django_db
def test_alias_records(api_client, zone):
    alias_record = route53.Record(
        name='alias',
        type='A',
        alias_target={
            'HostedZoneId': zone.r53_zone.id,
            'DNSName': 'test.%s' % zone.root,
            'EvaluateTargetHealth': False
        },
        zone=zone.r53_zone,
    )
    alias_record.save()
    zone.r53_zone.commit()
    response = api_client.get(
        '/zones/%s' % zone.id,
    )

    def sort_key(record):
        return record['name']

    rec_dict = get_record_from_base(alias_record, zone, managed=True)

    response_data = sorted(strip_ns_and_soa(response.data['records']), key=sort_key)
    assert response_data[0]['values'] == ['ALIAS test.test-zinc.net.']
    assert response_data == sorted([
        rec_dict,
        get_test_record(zone),
    ], key=sort_key)


@pytest.mark.django_db
def test_validation_prefix(api_client, zone):
    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data={
            'name': '_zn_something',
            'ttl': 300,
            'type': 'CNAME',
            'values': ['www.google.com']
        }
    )

    assert response.data == {
        'name': ['Record _zn_something can\'t start with _zn. It\'s a reserved prefix.']
    }


def get_ns(records):
    for record in records:
        if record.type == 'NS':
            # TODO: this is probably wrong if you have other NS records for zone delegation
            return record


@pytest.mark.django_db
def test_remove_a_managed_record(api_client, zone):
    ns = get_ns(zone.records)
    response = api_client.delete(
        '/zones/%s/records/%s' % (zone.id, ns.id)
    )

    assert response.status_code == 400
    assert response.data == ["Can't change a managed record."]


@pytest.mark.django_db
def test_create_a_new_SOA_record(api_client, zone):
    # SOA or whatever type that is not in the list.
    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data={
            'name': 'soa_record',
            'type': 'SOA',
            'ttl': 3000,
            'values': ['ns-774.awszinc-32.net.', 'awszinc-hostmaster.amazon.com.', '1',
                       '17200', '900', '1209600', '86400']
        }
    )
    assert response.status_code == 400
    assert response.data == {'type': ["Type 'SOA' is not allowed."]}


@pytest.mark.django_db
def test_create_NS_record(api_client, zone):
    ns = {
        'name': 'dev',
        'type': 'NS',
        'ttl': 3000,
        'values': ['ns-774.awszinc-32.net.', 'awszinc-hostmaster.amazon.com.']
    }
    response = api_client.post(
        '/zones/%s/records' % zone.id,
        data=ns
    )
    assert response.status_code == 201
    assert response.data == get_record_from_base(ns, zone)


@pytest.mark.django_db
def test_record_with_wrong_ipv4_values(api_client, zone):
    with patch('tests.fixtures.Moto.change_resource_record_sets') as mock_moto:
        mock_moto.side_effect = ClientError(
            error_response={
                'Error': {
                    'Code': 'InvalidChangeBatch',
                    'Message': "...ARRDATAIllegalIPv4Address...",
                    'Type': 'Sender'
                },
            },
            operation_name='change_resource_record_sets',
        )
        record = {
            'name': 'ipv4',
            'type': 'A',
            'ttl': 300,
            'values': ['300.0.0.1']
        }
        response = api_client.post(
            '/zones/%s/records' % (zone.id),
            data=record
        )
    assert response.status_code == 400
    assert response.data == {
        'values': ['Value is not a valid IPv4 address.']
    }


@pytest.mark.django_db
def test_record_with_wrong_ipv6_values(api_client, zone):
    with patch('tests.fixtures.Moto.change_resource_record_sets') as mock_moto:
        mock_moto.side_effect = ClientError(
            error_response={
                'Error': {
                    'Code': 'InvalidChangeBatch',
                    'Message': "...AAAARRDATAIllegalIPv6Address...",
                    'Type': 'Sender'
                },
            },
            operation_name='change_resource_record_sets',
        )
        record = {
            'name': 'ipv6',
            'ttl': 300,
            'type': 'AAAA',
            'values': ['xx:xx:xx:']
        }
        response = api_client.post(
            '/zones/%s/records' % (zone.id),
            data=record
        )
    assert response.status_code == 400
    assert response.data == {
        'values': ['Value is not a valid IPv6 address.']
    }


@pytest.mark.django_db
def test_forward_boto_errors(api_client, zone):
    with patch('tests.fixtures.Moto.change_resource_record_sets') as mock_moto:
        mock_moto.side_effect = ClientError(
            error_response={
                'Error': {
                    'Code': 'InvalidChangeBatch',
                    'Message': ("Invalid Resource Record: FATAL problem: "
                                "ARRDATANotSingleField (Value contains spaces) "
                                "encountered with 'trebuie sa crape'"),
                    'Type': 'Sender'
                },
            },
            operation_name='change_resource_record_sets',
        )
        record = {
            'name': 'side_effect',
            'type': 'A',
            'ttl': 300,
            'values': ['trebuie sa crape']
        }
        response = api_client.post(
            '/zones/%s/records' % zone.id,
            data=record
        )
    assert response.status_code == 400
    assert response.data == {
        'non_field_error': [
            ("Invalid Resource Record: FATAL problem: ARRDATANotSingleField "
             "(Value contains spaces) encountered with 'trebuie sa crape'")
        ]
    }


@pytest.mark.django_db
def test_txt_record_escape(zone, api_client):
    texts = sorted([
        r'simple',
        r'"duoble quoted"',
        r"'single quoted'",
        r'back\slash',
        r'escaped \"double quote'
    ])
    route53.Record(
        name='text',
        ttl=300,
        type='TXT',
        values=texts,
        zone=zone.r53_zone,
    ).save()
    zone.r53_zone.commit()
    response = api_client.get(
        '/zones/%s' % zone.id,
    )

    record = list(filter(lambda record: record['name'] == 'text',
                  response.data['records']))[0]

    assert sorted(record['values']) == texts
