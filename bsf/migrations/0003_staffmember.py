# Generated by Django 5.1.3 on 2024-11-29 20:17

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bsf', '0002_alter_farm_established_date'),
        ('company', '0003_alter_staff_work_email_alter_staff_work_phone'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StaffMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.CharField(choices=[('worker', 'Worker'), ('manager', 'Manager'), ('director', 'Director'), ('managing_director', 'Managing Director')], max_length=20)),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active', max_length=10)),
                ('level', models.IntegerField(choices=[(1, 'Level 1'), (2, 'Level 2'), (3, 'Level 3'), (4, 'Level 4'), (5, 'Level 5')], default=1)),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='staff_members', to='company.company')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_staff_assignments', to=settings.AUTH_USER_MODEL)),
                ('farm', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='staff_members', to='bsf.farm')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='staff_members', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'farm', 'company', 'status')},
            },
        ),
    ]