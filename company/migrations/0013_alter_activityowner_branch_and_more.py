# Generated by Django 5.1.3 on 2024-12-24 17:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0012_alter_activityowner_branch_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='activityowner',
            name='branch',
            field=models.CharField(default=1, max_length=255),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='activityowner',
            name='company',
            field=models.CharField(default=1, max_length=255),
            preserve_default=False,
        ),
    ]
