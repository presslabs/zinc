#!/bin/sh
set -eo pipefail

LOG_LEVEL=${ZINC_LOG_LEVEL:-INFO}

case "$1" in
    "web")         exec su-exec zinc gunicorn django_project.wsgi --bind "$ZINC_WEB_ADDRESS";;
    "celery")      exec su-exec zinc celery -A django_project worker --concurrency=4;;
    "celerybeat")  exec su-exec zinc celery -A django_project beat;;
esac

exec "$@"
