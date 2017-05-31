from collections import OrderedDict
import uuid
import logging

from botocore.exceptions import ClientError
from django.db import transaction
from django.conf import settings

from .record import Record
from .policy import Policy
from .client import get_client


logger = logging.getLogger(__name__)


class Zone(object):

    def __init__(self, db_zone):
        self.db_zone = db_zone
        self._aws_records = None
        self._exists = None
        self._change_batch = []
        self._client = get_client()

    @property
    def id(self):
        return self.db_zone.route53_id

    @property
    def root(self):
        return self.db_zone.root

    def process_records(self, records):
        for record in records:
            self._add_record_changes(record)

    def _add_record_changes(self, record):
        if record.deleted:
            action = 'DELETE'
        else:
            if record.created is True:
                action = 'CREATE'
            else:
                action = 'UPSERT'

        self._change_batch.append({
            'Action': action,
            'ResourceRecordSet': record.to_aws()
        })

    def _reset_change_batch(self):
        self._change_batch = []

    def commit(self, preserve_cache=False):
        if not preserve_cache:
            self._clear_cache()
        if not self._change_batch:
            return

        try:
            self._client.change_resource_record_sets(
                HostedZoneId=self.id,
                ChangeBatch={'Changes': self._change_batch}
            )
        except ClientError as excp:
            if excp.response['Error']['Code'] == 'InvalidInput':
                logging.exception("failed to process batch %r", self._change_batch)
            raise
        self._reset_change_batch()

    def records(self):
        self._cache_aws_records()
        entries = OrderedDict()
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
            self._clear_cache()
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
        self.db_zone.delete()

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
        if self.db_zone.caller_reference is None:
            self.db_zone.caller_reference = uuid.uuid4()
            self.db_zone.save()
        zone = self._client.create_hosted_zone(
            Name=self.root,
            CallerReference=str(self.db_zone.caller_reference),
            HostedZoneConfig={
                'Comment': getattr(settings, 'ZONE_OWNERSHIP_COMMENT', 'zinc')
            }
        )
        self.db_zone.route53_id = zone['HostedZone']['Id']
        self.db_zone.save()

    def _reconcile_zone(self):
        """
        Handles zone creation/deletion.
        """
        if self.db_zone.deleted:
            self.delete()
        elif self.db_zone.route53_id is None:
            self.create()
        elif not self.exists:
            try:
                self.create()
            except ClientError as excp:
                if excp.response['Error']['Code'] != 'HostedZoneAlreadyExists':
                    raise
                # This can happen if a zone was manually deleted from AWS.
                # Create will fail because we re-use the caller_reference
                self.db_zone.caller_reference = None
                self.db_zone.save()
                self.create()

    def check_policy_trees(self):
        clean_policy_records = self.db_zone.policy_records.filter(dirty=False)
        clean_policies = set([policy_record.policy for policy_record in clean_policy_records])
        assert self._change_batch == []
        for policy in clean_policies:
            r53_policy = Policy(policy=policy, zone=self)
            r53_policy.reconcile()
            if self._change_batch:
                logger.error("Glitch in the matrix for %s %s", self.root, policy.name)
                self._change_batch = []

    def _reconcile_policy_records(self):
        """
        Reconcile policy records for this zone.
        """
        with self.db_zone.lock_dirty_policy_records() as dirty_policy_records:
            dirty_policies = set()
            for policy_record in dirty_policy_records:
                if not policy_record.deleted:
                    dirty_policies.add(policy_record.policy)
            for policy in dirty_policies:
                r53_policy = Policy(policy=policy, zone=self)
                r53_policy.reconcile()
                self.commit(preserve_cache=True)
            for policy_record in dirty_policy_records:
                try:
                    with transaction.atomic():
                        policy_record.r53_policy_record.reconcile()
                        self.commit(preserve_cache=True)
                except ClientError as excp:
                    logger.exception("failed to reconcile record %r", policy_record)
                    self._reset_change_batch()
            self._delete_orphaned_managed_records()
            self.commit()

    def _delete_orphaned_managed_records(self):
        """Delete any managed record not belonging to one of the zone's policies"""
        active_policy_records = self.db_zone.policy_records.select_related('policy') \
                                                           .exclude(deleted=True)
        policies = set([pr.policy for pr in active_policy_records])
        for record in self.records().values():
            if record.is_hidden:
                for policy in policies:
                    if record.is_member_of(policy):
                        break
                else:
                    record.deleted = True
                    self.process_records([record])

    def reconcile(self):
        self._reconcile_zone()
        self._reconcile_policy_records()

    @classmethod
    def reconcile_multiple(cls, zones):
        for db_zone in zones:
            zone = cls(db_zone)
            try:
                zone.reconcile()
            except ClientError:
                logger.exception("Error while handling %s", db_zone.name)
