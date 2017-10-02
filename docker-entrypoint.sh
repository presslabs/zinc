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


exec_web(){
    if [ "$ZINC_MIGRATE" == "yes" ] ; then
        $DOCKERIZE su-exec zinc /app/manage.py migrate --noinput
    fi

    if [ "$ZINC_LOAD_DEV_DATA" == "yes" ] ; then
        $DOCKERIZE su-exec zinc /app/manage.py seed
    fi

    exec $DOCKERIZE su-exec zinc gunicorn django_project.wsgi --bind "$ZINC_WEB_ADDRESS" $@
}

case "$1" in
    "web")         exec_web;;
    "celery")      shift ; exec $DOCKERIZE su-exec zinc celery worker $@;;
    "celerybeat")  exec $DOCKERIZE su-exec zinc celery beat;;
esac

exec "$@"
