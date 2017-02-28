FROM python:3.5-alpine

ENV PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=zinc.settings

COPY . /app
RUN set -ex \
    && apk add --no-cache openssl \
        mariadb-client-libs \
    && addgroup -g 998 zinc \
    && adduser -SD -u 998 -G zinc -h /app zinc \
    && apk add --no-cache --virtual .build-deps \
        build-base \
        mariadb-dev \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && apk del .build-deps \
    && apk add --no-cache su-exec \
    && chown -R zinc:zinc /app

WORKDIR /app

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
