# Generated by Django 5.1.3 on 2024-11-29 03:05

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0002_alter_company_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='staff',
            name='work_email',
            field=models.EmailField(blank=True, max_length=254, null=True),
        ),
        migrations.AlterField(
            model_name='staff',
            name='work_phone',
            field=models.CharField(blank=True, max_length=20, null=True, validators=[django.core.validators.RegexValidator(message='Phone number must be valid and between 9-15 digits.', regex='^\\+?1?\\d{9,15}$')]),
        ),
    ]
