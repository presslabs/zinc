#!/usr/bin/env python3
import argparse
import os

import boto3

client = None


class Zone:
    def __init__(self, zone):
        self.zone = zone
        self.zone_id = zone['Id'].split('/')[2]

    @property
    def records(self):
        return client.list_resource_record_sets(HostedZoneId=self.zone_id)

    def destroy(self, dry_run=False):
        changes = []
        for record in self.records['ResourceRecordSets']:
            if record['Name'] == self.zone['Name'] and record['Type'] in ['NS', 'SOA']:
                continue
            changes.append({
                'Action': 'DELETE',
                'ResourceRecordSet': record
            })

        print('{} {} ({})'.format('Deleting' if dry_run else 'Will delete',
                                  self.zone['Name'], self.zone_id))
        if not dry_run:
            if changes:
                client.change_resource_record_sets(HostedZoneId=self.zone_id,
                                                   ChangeBatch={
                                                       'Changes': changes
                                                   })
            client.delete_hosted_zone(Id=self.zone_id)


class Zones:
    def __init__(self, limit_comment=None):
        self.limit_comment = limit_comment

    def __iter__(self):
        next_marker = ''
        while next_marker is not None:
            kwargs = {}
            if next_marker:
                kwargs = {'Marker': next_marker}
            response = client.list_hosted_zones(**kwargs)
            for zone in response['HostedZones']:
                if (self.limit_comment is None or
                        self.limit_comment == zone['Config'].get('Comment')):
                    yield Zone(zone)
            next_marker = response['NextMarker'] if response['IsTruncated'] else None


def parse_args():
    parser = argparse.ArgumentParser(description='Ansible inventory for lattice.')
    parser.add_argument('--limit-comment', '-l', default='zinc',
                        help='Remove only zones created using this comment. Defaults to \'zinc\'.')
    parser.add_argument('--dry-run', '-n', default=False, action='store_true',
                        help='Do not actually delete zones, just print the actions.')
    parser.add_argument('--aws-key', default=os.getenv('AWS_KEY', '-'),
                        help='AWS key to use. Defaults to AWS_KEY environment variable.')
    parser.add_argument('--aws-secret', default=os.getenv('AWS_SECRET', '-'),
                        help='AWS secret to use. Defaults to AWS_SECRET environment variable.')
    return parser.parse_args()


def main():
    global client
    args = parse_args()
    client = boto3.client('route53',
                          aws_access_key_id=args.aws_key,
                          aws_secret_access_key=args.aws_secret)

    for zone in Zones(limit_comment=args.limit_comment):
        zone.destroy(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
