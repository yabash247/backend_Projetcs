# Generated by Django 5.1.3 on 2025-01-08 23:08

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bsf', '0029_net_branch'),
        ('company', '0046_alter_expectations_uom'),
    ]

    operations = [
        migrations.AddField(
            model_name='farm',
            name='branch',
            field=models.ForeignKey(default=1, help_text='The branch to which the Net is assigned.', on_delete=django.db.models.deletion.CASCADE, related_name='farms', to='company.branch'),
            preserve_default=False,
        ),
    ]
