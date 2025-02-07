# Generated by Django 5.1.3 on 2025-01-02 09:03

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0033_activitydefaultsetting_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='activitydefaultsetting',
            name='description',
            field=models.TextField(blank=True, help_text='Description of the activity default setting.', null=True),
        ),
        migrations.AddField(
            model_name='activitydefaultsetting',
            name='min_duration',
            field=models.DurationField(default=datetime.timedelta(days=1), help_text='Estimated Minimum duration for the activity per count.'),
        ),
        migrations.AlterField(
            model_name='activitydefaultsetting',
            name='min_count',
            field=models.PositiveIntegerField(help_text='Estimated Minimum count/amount/times the activity needs to be performed monthly.'),
        ),
    ]
