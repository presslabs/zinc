from django.core.management.base import BaseCommand

from zinc import tasks


class Command(BaseCommand):
    help = 'Rebuild trees for any zone that has a dirty PolicyRecord'

    def handle(self, *args, **options):
        tasks.reconcile_policy_records.apply()
