# Generated by Django 5.1.3 on 2024-12-13 03:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bsf', '0017_alter_pondusestats_harvest_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pondusestats',
            name='harvest_stage',
            field=models.CharField(choices=[('Incubation', 'Incubation'), ('Nursery', 'Nursery'), ('Growout', 'Growout'), ('PrePupa', 'PrePupa'), ('Pupa', 'Pupa')], max_length=20, verbose_name='Harvest Stage'),
        ),
    ]