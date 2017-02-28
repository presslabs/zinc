#!/bin/sh
set -eo pipefail

echo $@
case "$1" in
    "web")         exec su-exec zinc gunicorn zinc.wsgi --bind 0.0.0.0:8000;;
    "celery")      exec su-exec zinc celery -A zinc worker -l info --config=zinc.settings;;
    "celerybeat")  exec su-exec zinc celery -A zinc beat -l info --config=zinc.settings;;
esac

exec "$@"
