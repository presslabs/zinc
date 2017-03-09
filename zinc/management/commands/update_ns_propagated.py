from django.core.management.base import BaseCommand

from zinc.models import Zone


class Command(BaseCommand):
    help = 'Update Zone.ns_propagated for all zones'

    def handle(self, *args, **options):
        Zone.update_ns_propagated()
        print("Done!")
