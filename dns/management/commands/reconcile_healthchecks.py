import logging

from django.core.management.base import BaseCommand

from dns.models import IP
from dns.utils.route53 import HealthCheck


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Reconcile all ip healthchecks'

    def handle(self, *args, **options):
        HealthCheck.reconcile_for_ips(IP.objects.all())
