# Generated by Django 5.1.3 on 2025-01-08 03:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0045_expectations'),
    ]

    operations = [
        migrations.AlterField(
            model_name='expectations',
            name='uom',
            field=models.CharField(choices=[('kg', 'Kilograms'), ('g', 'Grams'), ('pcs', 'Pieces'), ('percentage', 'Percentage'), ('l', 'Liters')], default='pcs', help_text='Unit of Measurement (UOM).', max_length=10),
        ),
    ]
