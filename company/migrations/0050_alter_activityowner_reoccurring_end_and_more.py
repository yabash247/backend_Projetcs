# Generated by Django 5.1.3 on 2025-02-06 23:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0049_activityowner_reoccurring_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='activityowner',
            name='reoccurring_End',
            field=models.DateField(blank=True, help_text='latest reoccuring end date. Only requireed if reoccuring is checked', null=True),
        ),
        migrations.AlterField(
            model_name='activityowner',
            name='reoccurring_Start',
            field=models.DateField(blank=True, help_text='latest reoccuring start date. Only requireed if reoccuring is checked', null=True),
        ),
    ]
