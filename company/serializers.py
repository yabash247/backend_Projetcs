from rest_framework import serializers
from .models import Company, Authority, Staff, StaffLevels

class StaffLevelsSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaffLevels
        fields = '__all__'
        read_only_fields = ['id', 'user ', 'company ']

    

class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = [
            'id', 'user', 'company', 'work_phone', 'work_email',
            'date_created', 'joined_company_date', 'comments', 'added_by', 'approved_by'
        ]
        read_only_fields = ['id', 'date_created', 'added_by']

class AuthoritySerializer(serializers.ModelSerializer):
    class Meta:
        model = Authority
        #fields = '__all__'
        fields = [
            'id', 'model_name', 'company', 'requested_by', 'approver',
            'view', 'add', 'edit', 'delete', 'accept', 'approve', 'created'
        ]
        read_only_fields = ['id', 'created', 'requested_by']

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'description', 'creator', 'approver', 'phone', 'email', 'website', 'comments', 'status']
        read_only_fields = ['id', 'creator']  # Creator is set automatically in the view

class AdminCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'description', 'creator', 'approver', 'phone', 'email', 'website', 'comments', 'status']
        read_only_fields = ['id', 'creator']