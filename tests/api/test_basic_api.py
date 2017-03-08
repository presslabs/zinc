# pylint: disable=no-member,protected-access,redefined-outer-name
import re

import pytest
from django_dynamic_fixture import G

from tests.fixtures import api_client  # noqa: F401
from zinc import models as m


@pytest.mark.django_db
def test_header_pagination(api_client):
    for _ in range(2):
        G(m.Policy)
    page1 = api_client.get('/policies', {'page_size': 1, 'page': 1})
    assert 'Link' in page1, 'Response is missing Link header'
    assert page1.status_code == 200, page1
    assert 'rel="next"' in page1['Link'], 'Response is missing rel="next" link header {}'.format(page1['Link'])  # noqa

    match = re.search(r'(http://.*); rel="next"', page1['Link'])
    assert match, "Invalid link header: {}".format(page1['Link'])

    page2 = api_client.get(match.group(1))
    assert page2.status_code == 200, page2.request
