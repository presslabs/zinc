#!/bin/sh
set -eo pipefail

LOG_LEVEL=${ZINC_LOG_LEVEL:-INFO}

case "$1" in
    "web")         exec su-exec zinc gunicorn zinc.wsgi --bind 0.0.0.0:8000;;
    "celery")      exec su-exec zinc celery -A zinc worker --loglevel="$LOG_LEVEL" --config=zinc.settings --concurrency=1;;
    "celerybeat")  exec su-exec zinc celery -A zinc beat --loglevel="$LOG_LEVEL" --config=zinc.settings;;
esac

exec "$@"
