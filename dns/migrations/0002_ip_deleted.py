# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-01 12:49
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dns', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='ip',
            name='deleted',
            field=models.BooleanField(default=False),
        ),
    ]
