import celery
from django.conf import settings


class Celery(celery.Celery):
    def _configure_sentry(self, raven_config):
        import raven
        from raven.contrib.celery import (register_signal,
                                          register_logger_signal)
        client = raven.Client(**raven_config)

        # register a custom filter to filter out duplicate logs
        register_logger_signal(client)

        # hook into the Celery error handler
        register_signal(client)

    def on_configure(self):
        raven_config = getattr(settings, 'RAVEN_CONFIG', None)
        if raven_config:
            self._configure_sentry(raven_config)

app = Celery(__name__)
app.config_from_object('django.conf:settings')
app.autodiscover_tasks()
