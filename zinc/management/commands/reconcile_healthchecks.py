from django.core.management.base import BaseCommand

from zinc.models import IP
from zinc.route53 import HealthCheck


class Command(BaseCommand):
    help = 'Reconcile all ip healthchecks'

    def handle(self, *args, **options):
        HealthCheck.reconcile_for_ips(IP.objects.all())
