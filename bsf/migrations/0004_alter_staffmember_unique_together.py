# Generated by Django 5.1.3 on 2024-11-29 23:26

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bsf', '0003_staffmember'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='staffmember',
            unique_together=set(),
        ),
    ]
