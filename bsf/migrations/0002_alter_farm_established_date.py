# Generated by Django 5.1.3 on 2024-11-29 15:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bsf', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='farm',
            name='established_date',
            field=models.DateField(blank=True, help_text='Date the farm was established.', null=True),
        ),
    ]
