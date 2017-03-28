from collections import OrderedDict
import zinc.route53
from .record import Record, RECORD_PREFIX


class Policy:
    def __init__(self, zone, policy):
        assert isinstance(zone, zinc.route53.Zone)
        self.zone = zone
        self.policy = policy

    @property
    def name(self):
        return self.policy.name

    @property
    def aws_records(self):
        '''What we have in AWS'''
        return dict([
            (r_id, record) for (r_id, record) in self.zone.records().items()
            if record.is_member_of(self)
        ])

    @property
    def desired_records(self):
        '''The records we should have (the desired state of the world)'''
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
        policy_members = self.policy.members.exclude(enabled=False).exclude(ip__enabled=False)
        # ensure we always build region subtrees in alphabetical order; makes tests simpler
        regions = sorted(set([pm.region for pm in policy_members]))
        if len(regions) > 1:
            # Here is the case where are multiple regions
            records = self._build_lbr_tree(policy_members, regions=regions)
        elif len(regions) == 1:
            # Case with a single region
            records = self._build_weighted_tree(
                policy_members, region_suffixed=False)
        else:
            raise Exception(
                "Policy can't be applied. zone: '{}'; policy: '{}'".format(
                    self.zone, self
                )
            )
        return records

    def reconcile(self):
        aws_record_ids = self.aws_records.keys()
        desired_record_ids = self.desired_records.keys()
        to_delete = []
        for obsolete_rec_id in aws_record_ids - desired_record_ids:
            record = self.aws_records[obsolete_rec_id]
            record.deleted = True
            to_delete.append(record)
        self.zone.add_records(to_delete)
        to_create = []
        for rec_id in desired_record_ids:
            if rec_id not in aws_record_ids:
                to_create.append(self.desired_records[rec_id])
        self.zone.add_records(to_create)
        self.zone.commit()
