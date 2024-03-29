"""
Django settings for zinc project.

Generated by 'django-admin startproject' using Django 1.9.8.

For more information on this file, see
https://docs.djangoproject.com/en/1.9/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.9/ref/settings/
"""

import os
import environ
import warnings
from datetime import timedelta

try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

root = environ.Path(__file__) - 3  # two folder back (/a/b/ - 2 = /)
env = environ.Env(DEBUG=(bool, False))  # set default values and casting
environ.Env.read_env()  # reading .env file


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = root()
DATA_DIR = env.str('ZINC_DATA_DIR', default=PROJECT_ROOT)
WEBROOT_DIR = env.str('ZINC_WEBROOT_DIR', os.path.join(PROJECT_ROOT, 'webroot/'))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.9/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
DEFAULT_SECRET_KEY = 'p@7-h3(%-ile((1fz2ei42)o^a-!cse@kp9jnhrx6x75)#1x(r'
SECRET_KEY = env.str('ZINC_SECRET_KEY', default=DEFAULT_SECRET_KEY)
if SECRET_KEY == DEFAULT_SECRET_KEY:
    warnings.warn("You are using the default secret key. Please set "
                  "ZINC_SECRET_KEY in .env file")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('ZINC_DEBUG', True)
SERVE_STATIC = env.bool('ZINC_SERVE_STATIC', False)

ALLOWED_HOSTS = env.list('ZINC_ALLOWED_HOSTS',
                         default=['localhost', '127.0.0.1', '0.0.0.0', 'zinc.lo'])
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if os.getenv('POD_IP'):
    ALLOWED_HOSTS.append(os.getenv('POD_IP'))

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = env.str('ZINC_GOOGLE_OAUTH2_KEY', '')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = env.str('ZINC_GOOGLE_OAUTH2_SECRET', '')

# LATTICE

LATTICE_URL = env.str('ZINC_LATTICE_URL', '')
LATTICE_USER = env.str('ZINC_LATTICE_USER', '')
LATTICE_PASSWORD = env.str('ZINC_LATTICE_PASSWORD', '')
LATTICE_ROLES = env.list('ZINC_LATTICE_ROLES', default=['edge-node'])
LATTICE_ENV = env.str('ZINC_LATTICE_ENV', 'production')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'drf_yasg',
    'zinc',
]

if SOCIAL_AUTH_GOOGLE_OAUTH2_KEY:
    INSTALLED_APPS += ['social_django']
if LATTICE_URL:
    INSTALLED_APPS += ['lattice_sync']

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
)
if SOCIAL_AUTH_GOOGLE_OAUTH2_KEY:
    AUTHENTICATION_BACKENDS = (
        'social_core.backends.google.GoogleOAuth2',
    ) + AUTHENTICATION_BACKENDS
    LOGIN_URL = '/_auth/login/google-oauth2/'

    SOCIAL_AUTH_ADMIN_USER_SEARCH_FIELDS = ['username', 'first_name', 'email']
    SOCIAL_AUTH_ADMIN_EMAILS = env.list("ZINC_SOCIAL_AUTH_ADMIN_EMAILS", default=[])
    SOCIAL_AUTH_GOOGLE_OAUTH2_WHITELISTED_DOMAINS = env.list(
        "ZINC_SOCIAL_AUTH_GOOGLE_OAUTH2_WHITELISTED_DOMAINS", default=[])
    SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = [
        'profile',
    ]

    SOCIAL_AUTH_PIPELINE = (
        # Get the information we can about the user and return it in a simple
        # format to create the user instance later. On some cases the details are
        # already part of the auth response from the provider, but sometimes this
        # could hit a provider API.
        'social_core.pipeline.social_auth.social_details',

        # Get the social uid from whichever service we're authing thru. The uid is
        # the unique identifier of the given user in the provider.
        'social_core.pipeline.social_auth.social_uid',

        # Verifies that the current auth process is valid within the current
        # project, this is where emails and domains whitelists are applied (if
        # defined).
        'social_core.pipeline.social_auth.auth_allowed',

        # Checks if the current social-account is already associated in the site.
        'social_core.pipeline.social_auth.social_user',

        # Make up a username for this person, appends a random string at the end if
        # there's any collision.
        'social_core.pipeline.user.get_username',

        # Send a validation email to the user to verify its email address.
        # Disabled by default.
        # 'social_core.pipeline.mail.mail_validation',

        # Associates the current social details with another user account with
        # a similar email address. Disabled by default.
        # 'social_core.pipeline.social_auth.associate_by_email',

        # Create a user account if we haven't found one yet.
        'social_core.pipeline.user.create_user',

        # Set superuser and is_staff
        'django_project.social_auth_pipeline.set_user_perms',

        # Create the record that associates the social account with the user.
        'social_core.pipeline.social_auth.associate_user',

        # Populate the extra_data field in the social record with the values
        # specified by settings (and the default ones like access_token, etc).
        'social_core.pipeline.social_auth.load_extra_data',

        # Update the user record with any changed info from the auth service.
        'social_core.pipeline.user.user_details',
    )


MIDDLEWARE = [
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
if SOCIAL_AUTH_GOOGLE_OAUTH2_KEY:
    MIDDLEWARE += [
        'social_django.middleware.SocialAuthExceptionMiddleware',
    ]

ROOT_URLCONF = 'django_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(PROJECT_ROOT, 'templates/')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'django_project.wsgi.application'

DATABASES = {
    'default': env.db('ZINC_DB_CONNECT_URL', 'sqlite:///%s' % os.path.join(DATA_DIR, 'db.sqlite3'))
}

# Password validation
# https://docs.djangoproject.com/en/1.9/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/1.9/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/

STATIC_URL = env.str('ZINC_STATIC_URL', '/static/')
STATIC_ROOT = os.path.join(WEBROOT_DIR, 'static/')

# CELERY

REDIS_URL = env.str('ZINC_REDIS_CONNECT_URL', 'redis://localhost:6379')
BROKER_URL = env.str('ZINC_BROKER_URL', '{}/0'.format(REDIS_URL))
CELERY_RESULT_BACKEND = env.str('ZINC_CELERY_RESULT_BACKEND',
                                '{}/1'.format(REDIS_URL))
CELERYBEAT_SCHEDULE = {
    'reconcile_zones': {
        'task': 'zinc.tasks.reconcile_zones',
        'schedule': timedelta(seconds=10),
    },
    'update_ns_propagated': {
        'task': 'zinc.tasks.update_ns_propagated',
        'schedule': timedelta(minutes=10),
    },
    'check_clean_zones': {
        'task': 'zinc.tasks.check_clean_zones',
        'schedule': timedelta(minutes=15),
    },
}

if LATTICE_URL:
    CELERYBEAT_SCHEDULE.update({
        'lattice_sync': {
            'task': 'lattice_sync.tasks.lattice_sync',
            'schedule': 30
        },
    })

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERYD_HIJACK_ROOT_LOGGER = False

# Distributed lock server
LOCK_SERVER_URL = env.str('ZINC_LOCK_SERVER_URL', default='{}/2'.format(REDIS_URL))

# HASHIDS
HASHIDS_MIN_LENGTH = 0

REST_FRAMEWORK = {
    'PAGE_SIZE': 50,
    'DEFAULT_PAGINATION_CLASS': 'zinc.pagination.LinkHeaderPagination',
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.JSONParser',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'EXCEPTION_HANDLER': 'zinc.middleware.custom_exception_handler'
}

HEALTH_CHECK_CONFIG = {
    'Port': 80,
    'Type': 'HTTP',
    'ResourcePath': '/status',
    'FullyQualifiedDomainName': env.str('ZINC_HEALTH_CHECK_FQDN', 'node.presslabs.net.'),
}

ZINC_DEFAULT_TTL = env.int('ZINC_DEFAULT_TTL', default=300)
ZINC_NS_CHECK_RESOLVERS = env.list('ZINC_NS_CHECK_RESOLVERS', default=['8.8.8.8'])
ZONE_OWNERSHIP_COMMENT = env.str('ZINC_ZONE_OWNERSHIP_COMMENT', 'zinc')

AWS_KEY = env.str('ZINC_AWS_KEY', '')
AWS_SECRET = env.str('ZINC_AWS_SECRET', '')

# configure logging
LOG_LEVEL = env.str('ZINC_LOG_LEVEL', 'INFO')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(asctime)s %(message)-80s logger=%(name)s level=%(levelname)s '
                      'process=%(processName)s thread=%(threadName)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': LOG_LEVEL,
        },
    },
    'loggers': {
        'celery.task': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False
        },
        'zinc': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
        },
        'celery': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False
        },
        'django': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False
        },
    },
}

# https://docs.djangoproject.com/en/3.2/releases/3.2/#customizing-type-of-auto-created-primary-keys
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'


if env.str('ZINC_SENTRY_DSN', ''):
    import raven
    INSTALLED_APPS += ['raven.contrib.django.raven_compat']
    release = env.str('ZINC_RELEASE', 'git')
    if release == 'git':
        try:
            release = raven.fetch_git_sha(os.path.dirname(os.pardir)),
        except Exception as exc:
            import traceback
            traceback.print_exc(exc)
            release = 'git+UNKNOWN'
    RAVEN_CONFIG = {
        'dsn': env.str('ZINC_SENTRY_DSN', ''),
        # If you are using git, you can also automatically configure the
        # release based on the git info.
        'release': release,
        'environment': env.str('ZINC_ENV_NAME', ''),
    }

    # Sentry logging with celery is a real pain in the ass
    # https://github.com/getsentry/sentry/issues/4565
    LOGGING['handlers']['sentry'] = {
        'level': 'ERROR',
        'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler'
    }
    for logger in LOGGING['loggers']:
        LOGGING['loggers'][logger]['handlers'].append('sentry')


SWAGGER_ENABLED = env.bool('ZINC_SWAGGER_ENABLED', DEBUG)
