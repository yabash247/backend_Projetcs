# Generated by Django 5.1.3 on 2024-12-29 06:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bsf', '0020_alter_netusestats_created_at_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='netusestats',
            name='created_at',
            field=models.DateField(blank=True, null=True),
        ),
    ]
