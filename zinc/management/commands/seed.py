from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django_dynamic_fixture import G

from zinc import models


class Command(BaseCommand):
    help = 'Seed the DB'

    @transaction.atomic
    def handle(self, *a, **kwa):
        admin = get_user_model()(**{
            "pk": 1,
            "username": "admin",
            "password": make_password("admin"),
            "is_staff": True,
            "is_superuser": True
        })
        admin.save()

        G(models.IP, **{
            "ip": "138.68.67.220",
            "hostname": "test-ip-1",
            "friendly_name": "test-ip-1",
            "healthcheck_id": None,
            "enabled": True,
            "deleted": False
        })

        G(models.IP, **{
            "ip": "138.68.79.108",
            "hostname": "test-ip-2",
            "friendly_name": "test-ip-2",
            "healthcheck_id": None,
            "enabled": True,
            "deleted": False
        })

        G(models.Policy, **{
            "id": "aabb0610-36a4-4328-9879-338ab1813cfb",
            "name": "policy-one"
        })

        G(models.PolicyMember, **{
            "id": "5ae24136-7e2b-407b-9447-6fa70a7829df",
            "region": "us-east-1",
            "ip": "138.68.79.108",
            "policy": "aabb0610-36a4-4328-9879-338ab1813cfb",
            "weight": 10
        })

        G(models.PolicyMember, **{
            "id": "67999f8a-71f7-41f7-a73a-35a2c76895a6",
            "region": "eu-central-1",
            "ip": "138.68.67.220",
            "policy": "aabb0610-36a4-4328-9879-338ab1813cfb",
            "weight": 10
        })
