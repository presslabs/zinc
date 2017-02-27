FROM python:3.5-alpine

ENV DOCKERIZE_VERSION=v0.3.0 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=zinc.settings

COPY ./requirements.txt /requirements.txt
RUN set -ex \
    && apk add --no-cache openssl \
        mariadb-client-libs \
    && addgroup -g 998 zinc \
    && adduser -SD -u 998 -G zinc -h /app zinc \
    && wget https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && tar -C /usr/local/bin -xzvf dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && apk add --no-cache --virtual .build-deps \
        build-base \
        mariadb-dev \
    && pip install --no-cache-dir -r requirements.txt \
    && apk del .build-deps

COPY . /app
WORKDIR /app

CMD ["gunicorn", "zinc.wsgi", "--bind", "0.0.0.0:8000"]
