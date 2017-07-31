# pylint: disable=no-member,protected-access,redefined-outer-name
import re

import pytest
from django_dynamic_fixture import G

from tests.fixtures import Moto, api_client, boto_client  # noqa: F401
from zinc import models as m


@pytest.mark.django_db
def test_header_pagination(api_client):
    for _ in range(2):
        G(m.Policy)
    page1 = api_client.get('/policies', {'page_size': 1, 'page': 1})
    assert 'Link' in page1, 'Response is missing Link header'
    assert page1.status_code == 200, page1
    assert 'rel="next"' in page1['Link'], 'Response is missing rel="next" link header {}'.format(page1['Link'])  # noqa

    match = re.search(r'<(http://.*)>; rel="next"', page1['Link'])
    assert match, "Invalid link header: {}".format(page1['Link'])

    page2 = api_client.get(match.group(1))
    assert page2.status_code == 200, page2.request


class ThrottledMoto:
    def __init__(self, throttle):
        self._call_countdown = dict()
        self._proxied_moto = Moto()
        for method_name, throttle_after_numcalls in throttle.items():
            method = getattr(self._proxied_moto, method_name)
            assert method is not None, \
                "No such method to throttle '{}'".format(method_name)
            assert callable(method),\
                "Attribute '{}' is not a callable".format(method_name)
            self._call_countdown[method_name] = throttle_after_numcalls

    def __getattr__(self, attr_name):
        countdown = self._call_countdown.get(attr_name)
        if countdown is not None:
            if countdown == 0:
                raise self.exceptions.ThrottlingException(
                    error_response={
                        'Error': {
                            'Code': 'Throttled',
                            'Message': 'Hold your horses...',
                            'Type': 'Sender'
                        },
                    },
                    operation_name=attr_name,
                )
            else:
                self._call_countdown[attr_name] -= 1
        return getattr(self._proxied_moto, attr_name)

    def __hasattr__(self, attr_name):
        return hasattr(self._proxied_moto, attr_name)

    @classmethod
    def factory(cls, throttle):
        return lambda: cls(throttle)


@pytest.mark.django_db
@pytest.mark.parametrize(
    'boto_client', [
        ThrottledMoto.factory(throttle={'create_hosted_zone': 0})
    ], indirect=True)
def test_throttled(api_client, boto_client):
    root = 'example.com.presslabs.com.'
    resp = api_client.post(
        '/zones',
        data={
            'root': root,
        }
    )
    assert resp.status_code == 429, resp.data
