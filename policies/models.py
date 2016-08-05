from django.db import models

POLICIES = (
    ('dev', 'Developer Policy'),
)


class Policy(models.Model):
    ref = models.CharField(choices=POLICIES)
