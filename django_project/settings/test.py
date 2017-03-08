from django_project.settings import *  # noqa

SECRET_KEY = 'test-secret'
CELERY_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

REST_FRAMEWORK.update({  # noqa: F405
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',)
})

LOGGING['loggers']['zinc']['level'] = 'WARN'  # noqa: F405
