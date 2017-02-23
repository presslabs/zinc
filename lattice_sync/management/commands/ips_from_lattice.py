import logging

from django.core.management.base import BaseCommand

from lattice_sync import sync


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Imports IPs from a lattice server'

    def add_arguments(self, parser):
        parser.add_argument('--url', default='')
        parser.add_argument('--user', default='')
        parser.add_argument('--password', default='')

    def handle(self, *args, **options):
        lattice = sync.lattice_factory(options['url'],
                                       options['user'],
                                       options['password'])
        sync.sync(lattice)
