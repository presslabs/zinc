from django.core.management.base import BaseCommand

from dns import models
from dns.utils import route53


class Command(BaseCommand):
    help = 'Reconcile all ip healthchecks'

    def handle(self, *args, **options):
        route53.Zone.reconcile_multiple(
            models.Zone.objects.all())
