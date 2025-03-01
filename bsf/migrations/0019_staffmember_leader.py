# Generated by Django 5.1.3 on 2024-12-27 09:17

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bsf', '0018_alter_pondusestats_harvest_stage'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='staffmember',
            name='leader',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='staff_member_lead', to=settings.AUTH_USER_MODEL),
        ),
    ]
