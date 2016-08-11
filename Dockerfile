FROM python:3.6-alpine

RUN mkdir /app
WORKDIR /app

RUN pip install --upgrade boto3==1.4.0 Django==1.10 "djangorestframework<3.5" requests==2.10.0 zipa==0.3.0 \
        celery==3.1.23

VOLUME /app
COPY . /app

RUN pip install -r requirements.txt
RUN ./manage.py migrate

CMD [ "python", "./manage.py", "runserver", "0.0.0.0:8000" ]