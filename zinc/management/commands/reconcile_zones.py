from django.core.management.base import BaseCommand

from zinc import models
from zinc import route53


class Command(BaseCommand):
    help = 'Reconcile all ip healthchecks'

    def handle(self, *args, **options):
        route53.Zone.reconcile_multiple(
            models.Zone.objects.all())
