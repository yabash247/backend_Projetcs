# Generated by Django 5.1.3 on 2024-12-27 22:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0020_remove_task_complted_by_task_completed_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='activity',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='task',
            name='modelName',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
