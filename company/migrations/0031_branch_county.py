# Generated by Django 5.1.3 on 2025-01-02 00:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0030_staff_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='branch',
            name='county',
            field=models.CharField(blank=True, help_text='County where the branch is located.', max_length=255, null=True),
        ),
    ]
