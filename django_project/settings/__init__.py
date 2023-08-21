# flake8: noqa
try:
    from local_settings import *
except ModuleNotFoundError as e:
    if e.name != 'local_settings':
        raise
    from .base import *

