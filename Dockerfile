FROM python:3.5-alpine

RUN mkdir /app
WORKDIR /app

RUN set -ex && apk add --no-cache openssl
RUN cat /etc/group
RUN addgroup -g 998 zinc && adduser -SD -u 998 -G zinc zinc

ENV DOCKERIZE_VERSION v0.2.0
RUN wget https://github.com/jwilder/dockerize/releases/download/$DOCKERIZE_VERSION/dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz \
    && tar -C /usr/local/bin -xzvf dockerize-linux-amd64-$DOCKERIZE_VERSION.tar.gz

VOLUME /app
COPY . /app

RUN pip install -r requirements.txt

ENV PYTHONUNBUFFERED 1
USER zinc
CMD [ "python", "./manage.py", "runserver", "0.0.0.0:8000" ]
