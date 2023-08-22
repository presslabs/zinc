#!/bin/bash
set -eo pipefail

exec_web(){
    if [ "$ZINC_MIGRATE" == "yes" ] ; then
        /app/manage.py migrate --noinput
    fi

    if [ "$ZINC_LOAD_DEV_DATA" == "yes" ] ; then
        /app/manage.py seed
    fi

    exec gunicorn django_project.wsgi --bind "$ZINC_WEB_ADDRESS" -k gevent $@
}

case "$1" in
    "web")         shift 1; exec_web $@;;
    "celery")      shift 1; exec celery worker $@;;
    "celerybeat")  shift 1; exec celery beat $@;;
esac

exec "$@"
