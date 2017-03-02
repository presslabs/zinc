try:
    from local_settings import *
except ImportError:
    from .base import *
