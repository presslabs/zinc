from urlparse import urlparse

from django.conf import settings

from zipa import lattice
from requests.auth import HTTPBasicAuth


LATTICE_URL = getattr(settings, 'LATTICE_URL',
                      'https://lattice.presslabs.net/')
LATTICE_USER = getattr(settings, 'LATTICE_USER', '')
LATTICE_PASS = getattr(settings, 'LATTICE_PASS', '')
parts = urlparse(LATTICE_URL)

if LATTICE_URL.startswith('http://'):
    lattice.config.secure = False

lattice.config.host = parts.netloc
lattice.config.prefix = parts.path
lattice.config.append_slash = True
lattice.config.auth = HTTPBasicAuth(LATTICE_USER, LATTICE_PASS)
