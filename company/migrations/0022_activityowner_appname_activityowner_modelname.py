# Generated by Django 5.1.3 on 2024-12-27 22:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0021_task_activity_task_modelname'),
    ]

    operations = [
        migrations.AddField(
            model_name='activityowner',
            name='appName',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='activityowner',
            name='modelName',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
