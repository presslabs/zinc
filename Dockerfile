FROM python:3.11-slim

ARG release=git
ENV ZINC_RELEASE "$release"

ENV PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=django_project.settings \
    ZINC_WEB_ADDRESS=0.0.0.0:8080 \
    CELERY_APP=django_project.vendors.celery

COPY ./requirements.txt /requirements.txt
RUN set -ex \
    && addgroup zinc \
    && adduser --system --disabled-password --ingroup zinc --shell /bin/bash --home /app zinc \
    && pip install --no-cache-dir -r /requirements.txt

COPY . /app
WORKDIR /app
USER zinc

RUN set -ex \
    && ZINC_SECRET_KEY="not-secure" /app/manage.py collectstatic --noinput


ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["web"]
