# Generated by Django 4.1.10 on 2023-08-22 11:52

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zinc', '0010_policy_ttl'),
    ]

    operations = [
        migrations.AlterField(
            model_name='policy',
            name='name',
            field=models.CharField(max_length=255, unique=True, validators=[django.core.validators.RegexValidator(code='invalid_policy_name', message='Policy name should contain only lowercase letters, numbers and hyphens', regex='^[a-z0-9-]+$')]),
        ),
    ]
