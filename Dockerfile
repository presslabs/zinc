FROM python:3.5-alpine

ENV PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=django_project.settings \
    ZINC_WEB_ADDRESS=0.0.0.0:8000

COPY ./requirements.txt /requirements.txt
RUN set -ex \
    && apk add --no-cache \
        make \
        mariadb-client-libs \
        openssl \
        su-exec \
    && addgroup -g 998 zinc \
    && adduser -SD -u 998 -G zinc -h /app zinc \
    && apk add --no-cache --virtual .build-deps \
        build-base \
        mariadb-dev \
    && pip install --no-cache-dir -r /requirements.txt \
    && apk del .build-deps \
    &&  wget -qO- https://github.com/jwilder/dockerize/releases/download/v0.4.0/dockerize-alpine-linux-amd64-v0.4.0.tar.gz | tar -zxf - -C /usr/bin \
    && chown root:root /usr/bin/dockerize

COPY . /app
WORKDIR /app

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["web"]
