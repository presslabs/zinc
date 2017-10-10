FROM python:3.5-alpine

ARG release=git
ENV ZINC_RELEASE "$release"

ENV PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=django_project.settings \
    ZINC_WEB_ADDRESS=0.0.0.0:8080 \
    CELERY_APP=django_project.vendors.celery

COPY ./requirements.txt /requirements.txt
RUN set -ex \
    && apk add --no-cache \
        make \
        openssl \
        su-exec \
    && addgroup -g 998 zinc \
    && adduser -SD -u 998 -G zinc -h /app zinc \
    && apk add --no-cache --virtual .build-deps \
        build-base \
    && pip install --no-cache-dir -r /requirements.txt \
    && apk del .build-deps \
    &&  wget -qO- https://github.com/jwilder/dockerize/releases/download/v0.4.0/dockerize-alpine-linux-amd64-v0.4.0.tar.gz | tar -zxf - -C /usr/bin \
    && chown root:root /usr/bin/dockerize

COPY . /app
WORKDIR /app

RUN set -ex \
    && ZINC_SECRET_KEY="not-secure" su-exec zinc /app/manage.py collectstatic --noinput


ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["web"]
