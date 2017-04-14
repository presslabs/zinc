from django.core.management.base import BaseCommand

from zinc import models
from zinc import route53
from zinc.route53.client import get_client


class Command(BaseCommand):
    help = 'Delete unknown r53 zones'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help='Only print which zones would be deleted',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        db_ids = set(models.Zone.objects.exclude(route53_id=None)
                     .values_list('route53_id', flat=True))
        client = get_client()
        paginator = client.get_paginator('list_hosted_zones')

        raw_zones = []
        for page in paginator.paginate():
            raw_zones.extend([
                zone for zone in page['HostedZones']
                if zone['Id'] not in db_ids])

        for raw_zone in raw_zones:
            db_zone = models.Zone(route53_id=raw_zone['Id'], root=raw_zone['Name'])
            zone = route53.Zone(db_zone)
            print('deleting {}'.format(zone))
            if not dry_run:
                zone.delete_from_r53()
