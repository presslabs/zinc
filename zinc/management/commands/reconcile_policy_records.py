from django.core.management.base import BaseCommand

from zinc import tasks


class Command(BaseCommand):
    help = 'Reconcile all ip healthchecks'

    def handle(self, *args, **options):
        tasks.reconcile_policy_records.apply()
