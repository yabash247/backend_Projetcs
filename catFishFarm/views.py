from company.models import Media, Company, Staff
from rest_framework import serializers, viewsets, generics, permissions
from .models import Farm, Pond, Batch, BatchMovement, StockingHistory, DestockingHistory, StaffMember
from users.models import UserProfile as Profile  # If Profile is actually named UserProfile
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.db.models import Prefetch
from rest_framework.permissions import IsAuthenticated
from company.utils import has_permission
from django.core.exceptions import PermissionDenied
from .serializers import FarmSerializer, PondSerializer, BatchSerializer, BatchMovementSerializer, StockingHistorySerializer, DestockingHistorySerializer, StaffMemberSerializer
import logging

logger = logging.getLogger(__name__)  # Set up logging

User = get_user_model()


def get_user_company(user, company_id=None):
    if company_id:
        print("company_id: ", company_id)
        try:
            company = Company.objects.get(id=company_id)
            if not user.staff_members.filter(company=company).exists():
                raise PermissionDenied("You are not a staff member of this company.")
            return company
        except Company.DoesNotExist:
            raise PermissionDenied("Invalid company ID provided.")
    
    # If no company_id is provided
    staff_companies = user.staff_members.values_list('company', flat=True)
    user_created_farms = Farm.objects.filter(created_by=user).values_list('company', flat=True)
    all_companies = set(staff_companies) | set(user_created_farms)
    if not all_companies:
        raise PermissionDenied("You are not associated with any company or have not created any farms.")
    
    #return Company.objects.filter(id__in=all_companies).first()
    return Company.objects.filter(id__in=all_companies).first() if all_companies else None

    # need to fix this later, user without a farm are been shown as not having the right auhotirty level instead off no farm associated to user.


def validate_company_and_farm(request):
    """
    Validates the company and farm IDs from request parameters.

    Args:
        request (HttpRequest): The request containing 'company' and 'farm' parameters.

    Returns:
        tuple: (Company instance, Farm instance)

    Raises:
        NotFound: If company or farm does not exist.
        PermissionDenied: If required parameters are missing.
    """
    company_id = request.query_params.get("company") or request.data.get("company")
    farm_id = request.query_params.get("farm") or request.data.get("farm")

    # ✅ Ensure required parameters are provided
    if not company_id:
        raise PermissionDenied("Error: 'company' query parameter is required.")
    if not farm_id:
        raise PermissionDenied("Error: 'farm' query parameter is required.")

    # ✅ Retrieve company and farm objects with a single query lookup
    farm = get_object_or_404(Farm.objects.select_related("company"), id=farm_id)

    # ✅ Ensure farm belongs to the specified company
    if farm.company.id != int(company_id):
        raise PermissionDenied("Error: The specified farm does not belong to the given company.")

    # ✅ Retrieve company object
    company = get_object_or_404(Company, id=company_id)

    return company, farm  # ✅ Return validated company and farm
    


class FarmViewSet(viewsets.ModelViewSet):
    queryset = Farm.objects.all()
    serializer_class = FarmSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        company_id = self.request.query_params.get('company')
        companies = get_user_company(self.request.user, company_id)  # May return multiple companies

        if isinstance(companies, Company):  # If a single company object is returned
            queryset = self.queryset.filter(company=companies)
        else:  # If multiple companies (queryset) are returned
            queryset = self.queryset.filter(company__in=companies)
            
        # Apply permission filtering
        allowed_queryset = has_permission(self.request.user, companies if isinstance(companies, Company) else companies.first(), 'catFishFarm', 'Farm', 'view', requested_documents=queryset)

        if isinstance(allowed_queryset, bool):  # Ensure queryset is returned
            return queryset if allowed_queryset else Farm.objects.none()
        
        return allowed_queryset

    def perform_create(self, serializer):
        company_id = self.request.data.get('company')
        company = get_user_company(self.request.user, company_id)

        if has_permission(self.request.user, company, 'catFishFarm', 'Farm', 'add'):
            serializer.save(created_by=self.request.user, company=company.id)
        else:
            raise PermissionDenied("You do not have permission to create farms.")

    def perform_update(self, serializer):
        farm = self.get_object()  # Get the existing farm instance
        company = farm.company  # Preserve the existing company

        # Ensure the user has permission to edit this farm
        if not has_permission(self.request.user, company, 'catFishFarm', 'Farm', 'edit'):
            raise PermissionDenied("You do not have permission to update this farm.")

        # Preserve existing values if not provided
        serializer.validated_data['company'] = company
        if 'name' not in serializer.validated_data:
            serializer.validated_data['name'] = farm.name

        # Save without triggering branch duplication
        serializer.save(created_by=self.request.user)


    def perform_destroy(self, instance):
        company_id = self.request.query_params.get('company')
        companies = get_user_company(self.request.user, company_id)

        # Ensure `companies` is a single `Company` instance (not a QuerySet)
        company = companies if isinstance(companies, Company) else companies.first()

        if not company:
            raise PermissionDenied("You do not have permission to delete this farm.")

        if has_permission(self.request.user, company, 'catFishFarm', 'Farm', 'delete'):
            instance.delete()
        else:
            raise PermissionDenied("You do not have permission to delete this farm.")


class StaffMemberViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Staff Members.
    """
    queryset = StaffMember.objects.all()
    serializer_class = StaffMemberSerializer
    permission_classes = [permissions.IsAuthenticated]

    queryset = StaffMember.objects.all()
    serializer_class = StaffMemberSerializer
    permission_classes = [permissions.IsAuthenticated]


    def get_queryset(self):
        """
        Retrieve staff members filtered by company and farm, enforcing user permissions.
        """
        company, farm = validate_company_and_farm(self.request)

        # ✅ Enforce user permission
        if not has_permission(self.request.user, company, "catFishFarm", "StaffMember", "view"):
            raise PermissionDenied("Error: You do not have permission to view staff members for this farm.")

        # ✅ Query staff members linked to the given company and farm
        queryset = StaffMember.objects.filter(company=company, farm=farm).select_related("user", "company")
        
        return queryset

        
    def perform_create(self, serializer):
        """
        Validate and create a new staff member after ensuring company and farm association.
        """
        company, farm = validate_company_and_farm(self.request)

        # ✅ Ensure user exists
        user_id = self.request.data.get("user")
        userStaff = User.objects.filter(id=user_id).first()
        if not userStaff:
            raise PermissionDenied("Error: Invalid user ID provided.")
        
        leader_id = self.request.data.get("leader")
        leader = User.objects.filter(id=leader_id).first()
        if not leader:
            raise PermissionDenied("Error: Invalid leader ID provided.") 

        # ✅ Check if user is a staff member of the company
        if not Staff.objects.filter(user=userStaff, company=company).exists():
            raise PermissionDenied("Error: User is not a staff member of this company.")

        # ✅ Check if user is already a staff member of this farm
        existing_staff_member = StaffMember.objects.filter(user=userStaff, farm=farm).first()
        if existing_staff_member:
            # Deactivate existing staff record before adding a new one
            existing_staff_member.status = "inactive"
            existing_staff_member.save()
            logger.info(f"Existing Staff Member {existing_staff_member.id} set to inactive.")

        # ✅ Enforce permission check
        if not has_permission(self.request.user, company, "catFishFarm", "StaffMember", "add"):
            raise PermissionDenied("Error: You do not have permission to add staff members.")

        # ✅ Assign `company` and `farm` before saving
        staff_member = serializer.save(
            created_by=self.request.user,
            farm=farm,
            company=company,
            user=userStaff,
            leader=leader,
        )

        # ✅ Logging for debugging
        logger.info(f"Staff Member {staff_member.id} added by {self.request.user} to farm {farm.id} in company {company.id}")


class PondViewSet(viewsets.ModelViewSet):
    queryset = Pond.objects.all()
    serializer_class = PondSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        company = get_user_company(self.request.user)
        if has_permission(self.request.user, company, 'catFishFarm', 'Pond', 'add'):
            serializer.save()
        else:
            raise PermissionDenied("You do not have permission to create ponds.")

    def perform_update(self, serializer):
        company = get_user_company(self.request.user)
        if has_permission(self.request.user, company, 'catFishFarm', 'Pond', 'edit'):
            serializer.save()
        else:
            raise PermissionDenied("You do not have permission to update this pond.")

    def perform_destroy(self, instance):
        company = get_user_company(self.request.user)
        if has_permission(self.request.user, company, 'catFishFarm', 'Pond', 'delete'):
            instance.delete()
        else:
            raise PermissionDenied("You do not have permission to delete this pond.")

class BatchViewSet(viewsets.ModelViewSet):
    queryset = Batch.objects.all()
    serializer_class = BatchSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        company = get_user_company(self.request.user)
        if has_permission(self.request.user, company, 'catFishFarm', 'Batch', 'add'):
            serializer.save()
        else:
            raise PermissionDenied("You do not have permission to create batches.")

    def perform_update(self, serializer):
        company = get_user_company(self.request.user)
        if has_permission(self.request.user, company, 'catFishFarm', 'Batch', 'edit'):
            serializer.save()
        else:
            raise PermissionDenied("You do not have permission to update this batch.")

    def perform_destroy(self, instance):
        company = get_user_company(self.request.user)
        if has_permission(self.request.user, company, 'catFishFarm', 'Batch', 'delete'):
            instance.delete()
        else:
            raise PermissionDenied("You do not have permission to delete this batch.")

class BatchMovementViewSet(viewsets.ModelViewSet):
    queryset = BatchMovement.objects.all()
    serializer_class = BatchMovementSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        company = get_user_company(self.request.user)
        if has_permission(self.request.user, company, 'catFishFarm', 'BatchMovement', 'add'):
            serializer.save()
        else:
            raise PermissionDenied("You do not have permission to move batches.")

class StockingHistoryViewSet(viewsets.ModelViewSet):
    queryset = StockingHistory.objects.all()
    serializer_class = StockingHistorySerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        company = get_user_company(self.request.user)
        if has_permission(self.request.user, company, 'catFishFarm', 'StockingHistory', 'add'):
            serializer.save()
        else:
            raise PermissionDenied("You do not have permission to create stocking history records.")

class DestockingHistoryViewSet(viewsets.ModelViewSet):
    queryset = DestockingHistory.objects.all()
    serializer_class = DestockingHistorySerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        company = get_user_company(self.request.user)
        if has_permission(self.request.user, company, 'catFishFarm', 'DestockingHistory', 'add'):
            serializer.save()
        else:
            raise PermissionDenied("You do not have permission to create destocking history records.")