# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2022-02-28 14:01
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zinc', '0009_auto_20220228_1318'),
    ]

    operations = [
        migrations.AddField(
            model_name='policy',
            name='ttl',
            field=models.PositiveIntegerField(default=30),
        ),
    ]
