# Generated by Django 5.1.3 on 2025-01-08 03:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bsf', '0023_staffmember_branch'),
    ]

    operations = [
        migrations.AddField(
            model_name='netusestats',
            name='expect_harvest',
            field=models.FloatField(default=0, help_text='Expected harvest weight in grams'),
        ),
    ]
