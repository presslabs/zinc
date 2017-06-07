from collections import OrderedDict
import zinc.route53
from zinc.utils import memoized_property
from .record import Record, RECORD_PREFIX


class Policy:
    def __init__(self, zone, policy):
        assert isinstance(zone, zinc.route53.Zone)
        self.zone = zone
        self.db_policy = policy

    @property
    def name(self):
        return self.db_policy.name

    @property
    def id(self):
        return self.db_policy.id

    @property
    def routing(self):
        return self.db_policy.routing

    @memoized_property
    def aws_records(self):
        """What we have in AWS"""
        return dict([
            (r_id, record) for (r_id, record) in self.zone.records().items()
            if record.is_member_of(self)
        ])

    @memoized_property
    def desired_records(self):
        """The records we should have (the desired state of the world)"""
        return OrderedDict([(record.id, record) for record in self._build_tree()])

    def _build_weighted_tree(self, policy_members, region_suffixed=True):
        # Build simple tree
        records = []
        for policy_member in policy_members:
            health_check_kwa = {}
            if policy_member.ip.healthcheck_id:
                health_check_kwa['health_check_id'] = str(policy_member.ip.healthcheck_id)
            record = Record(
                ttl=30,
                type='A',
                values=[policy_member.ip.ip],
                set_identifier='{}-{}'.format(str(policy_member.id), policy_member.region),
                weight=policy_member.weight,
                zone=self.zone,
                **health_check_kwa,
            )
            # TODO: maybe we should have a specialized subclass for PolicyRecords
            # and this logic should be moved there
            if region_suffixed:
                record.name = '{}_{}_{}'.format(RECORD_PREFIX, self.name, policy_member.region)
            else:
                record.name = '{}_{}'.format(RECORD_PREFIX, self.name)
            records.append(record)

        return records

    def _build_lbr_tree(self, policy_members, regions):
        # Build latency based routed tree
        records = self._build_weighted_tree(policy_members)
        for region in regions:
            record = Record(
                name='{}_{}'.format(RECORD_PREFIX, self.name),
                type='A',
                alias_target={
                    'HostedZoneId': self.zone.id,
                    'DNSName': '{}_{}_{}.{}'.format(
                        RECORD_PREFIX, self.name, region, self.zone.root),
                    'EvaluateTargetHealth': True  # len(regions) > 1
                },
                region=region,
                set_identifier=region,
                zone=self.zone,
            )
            records.append(record)
        return records

    def _build_tree(self):
        policy_members = self.db_policy.members.exclude(enabled=False).exclude(ip__enabled=False)
        # ensure we always build region subtrees in alphabetical order; makes tests simpler
        regions = sorted(set([pm.region for pm in policy_members]))
        if len(regions) == 0:
            raise Exception(
                "Policy can't be applied. zone: '{}'; policy: '{}'".format(
                    self.zone, self
                )
            )
        if self.routing == 'latency':
            # Here is the case where are multiple regions
            records = self._build_lbr_tree(policy_members, regions=regions)
        # elif len(regions) == 1:
        elif self.routing == 'weighted':
            # Case with a single region
            records = self._build_weighted_tree(
                policy_members, region_suffixed=False)
        else:
            raise AssertionError('invalid routing {} for policy {}'.format(
                self.routing, self.db_policy))
        return records

    def reconcile(self):
        aws_record_ids = self.aws_records.keys()
        desired_record_ids = self.desired_records.keys()
        to_delete = []
        for obsolete_rec_id in aws_record_ids - desired_record_ids:
            record = self.aws_records[obsolete_rec_id]
            record.deleted = True
            to_delete.append(record)
        self.zone.process_records(to_delete)
        to_upsert = []
        for rec_id, desired_record in self.desired_records.items():
            existing_record = self.aws_records.get(rec_id)
            if existing_record is None:
                to_upsert.append(desired_record)
            else:
                # if desired is a subset of existing
                if not desired_record.to_aws().items() <= existing_record.to_aws().items():
                    to_upsert.append(desired_record)
        self.zone.process_records(to_upsert)

    def remove(self):
        records = list(self.aws_records.values())
        for record in records:
            record.deleted = True
        self.zone.process_records(records)
