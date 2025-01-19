# Generated by Django 5.1.3 on 2025-01-08 03:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bsf', '0025_remove_netusestats_expect_harvest'),
    ]

    operations = [
        migrations.AddField(
            model_name='net',
            name='expect_harvest',
            field=models.FloatField(default=0, help_text='Expected harvest weight in grams'),
        ),
    ]
