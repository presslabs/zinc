from zinc.settings import *

SECRET_KEY = 'test-secret'
CELERY_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1']

LOGGING['loggers']['zinc']['level'] = 'WARN'
