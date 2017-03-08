# flake8: noqa
try:
    from local_settings import *
except ImportError as e:
    if e.name != 'local_settings':
        raise
    from .base import *

