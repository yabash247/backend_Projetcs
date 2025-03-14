# Generated by Django 5.1.3 on 2024-12-22 07:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0007_alter_company_creator'),
    ]

    operations = [
        migrations.AddField(
            model_name='media',
            name='creation_date',
            field=models.DateTimeField(blank=True, help_text='Date the video was created', null=True),
        ),
        migrations.AddField(
            model_name='media',
            name='creation_location',
            field=models.CharField(blank=True, help_text='Latitude and Longitude of the video', max_length=255, null=True),
        ),
    ]
