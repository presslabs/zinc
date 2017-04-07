#!/bin/sh
set -eo pipefail

LOG_LEVEL=${ZINC_LOG_LEVEL:-INFO}

DOCKERIZE=""

prefix="dockerize"

if [[ "$1" == $prefix ]];
then
    DOCKERIZE="dockerize"
    shift
    while [[ "$1" != '--' ]] ;
    do
        DOCKERIZE="$DOCKERIZE $1"
        shift
    done
    shift
fi


case "$1" in
    "web")         exec $DOCKERIZE su-exec zinc gunicorn django_project.wsgi --bind "$ZINC_WEB_ADDRESS";;
    "celery")      exec $DOCKERIZE su-exec zinc celery -A django_project worker --concurrency=4;;
    "celerybeat")  exec $DOCKERIZE su-exec zinc celery -A django_project beat;;
esac

exec "$@"
