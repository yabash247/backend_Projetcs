# Generated by Django 5.1.3 on 2025-01-15 09:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bsf', '0030_farm_branch'),
    ]

    operations = [
        migrations.AddField(
            model_name='pondusestats',
            name='laying_ratting',
            field=models.CharField(choices=[('outstanding', 'Outstanding'), ('exceeds_expectation', 'Exceeds Expectation'), ('satisfactory', 'Satisfactory'), ('unsatisfactory', 'Unsatisfactory'), ('poor', 'Poor')], default='unsatisfactory', max_length=40),
        ),
    ]
