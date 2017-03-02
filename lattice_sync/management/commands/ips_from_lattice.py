import logging

from django.core.management.base import BaseCommand
from django.conf import settings

from lattice_sync import sync


logger = logging.getLogger('zinc.cli')


class Command(BaseCommand):
    help = 'Imports IPs from a lattice server'

    def add_arguments(self, parser):
        parser.add_argument('--url', default=settings.LATTICE_URL)
        parser.add_argument('--user', default=settings.LATTICE_USER)
        parser.add_argument('--password', default=settings.LATTICE_PASSWORD)

    def handle(self, *args, **options):
        lattice = sync.lattice_factory(options['url'],
                                       options['user'],
                                       options['password'])
        sync.sync(lattice)
        logger.info("done")
