import os

from celery import Celery
from celery_once import QueueOnce

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zinc.settings')

from django.conf import settings  # noqa
from time import sleep

app = Celery('zinc')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))


@app.task(base=QueueOnce, once={'key': [], 'graceful': True})
def slow_task():
    sleep(30)
    return "Done!"