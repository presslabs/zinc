import uuid
import logging

from botocore.exceptions import ClientError
from django.conf import settings

from .client import get_client

logger = logging.getLogger('zinc.route53')


def generate_caller_ref():
    return 'zinc {}'.format(uuid.uuid4())


class HealthCheck:
    def __init__(self, ip):
        self.ip = ip
        self._aws_data = None
        self._client = get_client()

    @property
    def exists(self):
        self._load()
        return self._aws_data is not None

    @property
    def id(self):
        self._load()
        return self._aws_data.get('Id')

    def _load(self):
        if self._aws_data is not None:
            return
        if self.ip.healthcheck_id is not None:
            try:
                health_check = self._client.get_health_check(HealthCheckId=self.ip.healthcheck_id)
                self._aws_data = health_check.get('HealthCheck')
            except ClientError as exception:
                if exception.response['Error']['Code'] != 'NoSuchHealthCheck':
                    raise  # re-raise any error, we only handle non-existant health checks

    @property
    def desired_config(self):
        config = {
            'IPAddress': self.ip.ip,
        }
        config.update(settings.HEALTH_CHECK_CONFIG)
        return config

    @property
    def config(self):
        self._load()
        return self._aws_data.get('HealthCheckConfig')

    def create(self):
        if self.ip.healthcheck_caller_reference is None:
            self.ip.healthcheck_caller_reference = uuid.uuid4()
            logger.info("%-15s new caller_reference %s",
                        self.ip.ip, self.ip.healthcheck_caller_reference)
            self.ip.save()
        resp = self._client.create_health_check(
            CallerReference=str(self.ip.healthcheck_caller_reference),
            HealthCheckConfig=self.desired_config
        )
        self.ip.healthcheck_id = resp['HealthCheck']['Id']
        logger.info("%-15s created hc: %s", self.ip.ip, self.ip.healthcheck_id)
        self.ip.save()

    def delete(self):
        if self.exists:
            logger.info("%-15s delete hc: %s", self.ip.ip, self.ip.healthcheck_id)
            self._client.delete_health_check(HealthCheckId=self.id)
            self.ip.healthcheck_caller_reference = None
            self.ip.save(update_fields=['healthcheck_caller_reference'])

    def reconcile(self):
        if self.ip.deleted:
            self.delete()
            self.ip.delete()
        elif self.exists:
            # if the desired config is not a subset of the current config
            if not self.desired_config.items() <= self.config.items():
                self.delete()
                self.create()
            else:
                logger.info("%-15s nothing to do", self.ip.ip)
        else:
            try:
                self.create()
            except ClientError as excp:
                if excp.response['Error']['Code'] != 'HealthCheckAlreadyExists':
                    raise
                self.ip.healthcheck_caller_reference = None
                self.ip.save()
                self.create()

    @classmethod
    def reconcile_for_ips(cls, ips):
        checks = [cls(ip) for ip in ips]
        for check in checks:
            try:
                check.reconcile()
            except ClientError:
                logger.exception("Error while handling %s", check.ip.friendly_name)
