import uuid
import logging

from botocore.exceptions import ClientError

from .record import Record
from .client import get_client

logger = logging.getLogger(__name__)


class Zone(object):

    def __init__(self, zone_record):
        self.zone_record = zone_record
        self._aws_records = None
        self._exists = None
        self._change_batch = []
        self._client = get_client()

    @property
    def id(self):
        return self.zone_record.route53_id

    @property
    def root(self):
        return self.zone_record.root

    def add_records(self, records):
        for record in records:
            self.add_record_changes(record, key=record.id)

    def add_record_changes(self, record, key=None):
        rrs = record.encode()
        if not key or key not in self.records():
            action = 'CREATE'
        else:
            action = 'DELETE' if record.deleted else 'UPSERT'

        self._change_batch.append({
            'Action': action,
            'ResourceRecordSet': rrs
        })

    def _reset_change_batch(self):
        self._change_batch = []

    def commit(self):
        if not self._change_batch:
            return

        self._client.change_resource_record_sets(
            HostedZoneId=self.id,
            ChangeBatch={'Changes': self._change_batch}
        )
        # clear cache
        self._reset_change_batch()
        self._clear_cache()

    def records(self):
        self._cache_aws_records()
        entries = {}
        for aws_record in self._aws_records or []:
            record = Record.from_aws_record(aws_record, zone=self)
            if record:
                entries[record.id] = record
        return entries

    @property
    def exists(self):
        self._cache_aws_records()
        return self._exists

    @property
    def ns(self):
        if not self.exists:
            return None
        ns = [record for record in self.records().values()
              if record.type == 'NS' and record.name == '@']
        assert len(ns) == 1
        return ns[0]

    def _cache_aws_records(self):
        if self._aws_records is not None:
            return
        if not self.id:
            return
        paginator = self._client.get_paginator('list_resource_record_sets')
        records = []
        try:
            for page in paginator.paginate(HostedZoneId=self.id):
                records.extend(page['ResourceRecordSets'])
        except ClientError as excp:
            if excp.response['Error']['Code'] != 'NoSuchHostedZone':
                raise
            self._aws_records = []
            self._exists = False
        else:
            self._aws_records = records
            self._exists = True

    def _clear_cache(self):
        self._aws_records = None
        self._exists = None

    def delete(self):
        if self.exists:
            self._delete_records()
            self._client.delete_hosted_zone(Id=self.id)
        self.zone_record.delete()

    def _delete_records(self):
        self._cache_aws_records()
        zone_root = self.root

        to_delete = []
        for record in self._aws_records:
            if record['Type'] in ['NS', 'SOA'] and record['Name'] == zone_root:
                continue

            to_delete.append({
                'Action': 'DELETE',
                'ResourceRecordSet': record
            })

        if to_delete:
            self._client.change_resource_record_sets(
                HostedZoneId=self.id,
                ChangeBatch={
                    'Changes': to_delete
                })

    def create(self):
        if self.zone_record.caller_reference is None:
            self.zone_record.caller_reference = uuid.uuid4()
            self.zone_record.save()
        zone = self._client.create_hosted_zone(
            Name=self.root,
            CallerReference=str(self.zone_record.caller_reference),
            HostedZoneConfig={
                'Comment': 'zinc'
            }
        )
        self.zone_record.route53_id = zone['HostedZone']['Id']
        self.zone_record.save()

    def reconcile(self):
        if self.zone_record.deleted:
            self.delete()
        elif self.zone_record.route53_id is None:
            self.create()
        elif not self.exists:
            try:
                self.create()
            except ClientError as excp:
                if excp.response['Error']['Code'] != 'HostedZoneAlreadyExists':
                    raise
                # This can happen if a zone was manually deleted from AWS.
                # Create will fail because we re-use the caller_reference
                self.zone_record.caller_reference = None
                self.zone_record.save()
                self.create()

    @classmethod
    def reconcile_multiple(cls, zones):
        for zone_record in zones:
            zone = cls(zone_record)
            try:
                zone.reconcile()
            except ClientError:
                logger.exception("Error while handling %s", zone_record.name)
