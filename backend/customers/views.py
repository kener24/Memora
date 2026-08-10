from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView

from core.responses import success_response
from organizations.models import Branch, Organization

from .access import get_customer_permissions, is_global_customer_user, scope_branches, scope_customers
from .choices import ActivityAction, Gender, HondurasDepartment, MaritalStatus, Relationship
from .models import Beneficiary, Customer, CustomerContact
from .pagination import CustomerPagination
from .permissions import BeneficiaryPermission, ContactPermission, CustomerPermission
from .serializers import (
    BeneficiarySerializer,
    CustomerContactSerializer,
    CustomerCreateUpdateSerializer,
    CustomerDetailSerializer,
    CustomerListSerializer,
    DuplicateCheckSerializer,
)
from .services import allocate_customer_code, record_activity, switch_primary_contact


class CustomerViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = (CustomerPermission,)
    pagination_class = CustomerPagination
    filter_backends = (filters.SearchFilter,)
    search_fields = (
        "customer_code", "first_name", "middle_name", "last_name", "second_last_name",
        "identity_number", "phone", "secondary_phone", "email",
    )
    http_method_names = ("get", "post", "patch", "head", "options")

    def get_queryset(self):
        queryset = Customer.objects.select_related(
            "organization", "branch", "created_by"
        ).prefetch_related("beneficiaries", "contacts", "activities__user")
        queryset = scope_customers(queryset, self.request.user)
        if self.action != "list":
            return queryset

        params = self.request.query_params
        is_active = params.get("is_active")
        if is_active in {"true", "false"}:
            queryset = queryset.filter(is_active=is_active == "true")
        if params.get("branch"):
            queryset = queryset.filter(branch_id=params["branch"])
        if params.get("department"):
            queryset = queryset.filter(department=params["department"])
        created_from = parse_date(params.get("created_from", ""))
        created_to = parse_date(params.get("created_to", ""))
        if created_from:
            queryset = queryset.filter(created_at__date__gte=created_from)
        if created_to:
            queryset = queryset.filter(created_at__date__lte=created_to)

        ordering_map = {
            "name": ("first_name", "last_name"),
            "-name": ("-first_name", "-last_name"),
            "customer_code": ("customer_code",),
            "-customer_code": ("-customer_code",),
            "created_at": ("created_at",),
            "-created_at": ("-created_at",),
            "updated_at": ("updated_at",),
            "-updated_at": ("-updated_at",),
        }
        ordering = ordering_map.get(params.get("ordering"), ("-created_at",))
        return queryset.annotate(
            beneficiaries_count=Count("beneficiaries", filter=Q(beneficiaries__is_active=True), distinct=True)
        ).order_by(*ordering)

    def get_serializer_class(self):
        if self.action == "list":
            return CustomerListSerializer
        if self.action in {"create", "partial_update", "update"}:
            return CustomerCreateUpdateSerializer
        return CustomerDetailSerializer

    def retrieve(self, request, *args, **kwargs):
        customer = self.get_object()
        return success_response(CustomerDetailSerializer(customer).data, "Cliente obtenido correctamente.")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                organization = serializer.validated_data["organization"]
                customer = serializer.save(
                    customer_code=allocate_customer_code(organization),
                    created_by=request.user,
                )
                record_activity(customer, request.user, ActivityAction.CREATED)
        except IntegrityError as exc:
            raise ValidationError({"detail": "No fue posible asignar un código único al cliente."}) from exc
        return success_response(
            CustomerDetailSerializer(customer).data,
            "Cliente registrado correctamente.",
            status=status.HTTP_201_CREATED,
        )

    def partial_update(self, request, *args, **kwargs):
        customer = self.get_object()
        serializer = self.get_serializer(customer, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            customer = serializer.save()
            record_activity(customer, request.user, ActivityAction.UPDATED)
        return success_response(CustomerDetailSerializer(customer).data, "Información actualizada.")

    @action(detail=True, methods=("post",))
    def activate(self, request, pk=None):
        customer = self.get_object()
        if customer.is_active:
            return success_response(CustomerDetailSerializer(customer).data, "El cliente ya está activo.")
        if customer.identity_number and Customer.objects.filter(
            organization=customer.organization,
            identity_number=customer.identity_number,
            is_active=True,
        ).exclude(pk=customer.pk).exists():
            raise ValidationError({"identity_number": "Otro cliente activo utiliza esta identidad."})
        with transaction.atomic():
            customer.is_active = True
            customer.save(update_fields=("is_active", "updated_at"))
            record_activity(customer, request.user, ActivityAction.ACTIVATED)
        return success_response(CustomerDetailSerializer(customer).data, "Cliente reactivado.")

    @action(detail=True, methods=("post",))
    def deactivate(self, request, pk=None):
        customer = self.get_object()
        if not customer.is_active:
            return success_response(CustomerDetailSerializer(customer).data, "El cliente ya está inactivo.")
        with transaction.atomic():
            customer.is_active = False
            customer.save(update_fields=("is_active", "updated_at"))
            record_activity(customer, request.user, ActivityAction.DEACTIVATED)
        return success_response(CustomerDetailSerializer(customer).data, "Cliente inactivado.")

    @action(detail=False, methods=("post",), url_path="check-duplicates")
    def check_duplicates(self, request):
        serializer = DuplicateCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        queryset = scope_customers(Customer.objects.all(), request.user)
        identity = serializer.validated_data.get("identity_number")
        phone = serializer.validated_data.get("phone")
        matches = []
        if identity:
            matches.extend(queryset.filter(identity_number=identity, is_active=True)[:5])
        if phone:
            matches.extend(queryset.filter(phone=phone)[:5])
        unique_matches = {customer.pk: customer for customer in matches}.values()
        return success_response(
            [
                {
                    "id": item.pk,
                    "customer_code": item.customer_code,
                    "full_name": item.full_name,
                    "same_identity": bool(identity and item.identity_number == identity),
                    "same_phone": bool(phone and item.phone == phone),
                }
                for item in unique_matches
            ],
            "Coincidencias verificadas.",
        )

    @action(detail=False, methods=("get",), url_path="options")
    def module_options(self, request):
        branches = scope_branches(Branch.objects.filter(is_active=True), request.user).select_related("organization")
        organizations = Organization.objects.filter(is_active=True).order_by("name") if is_global_customer_user(request.user) else []
        return success_response(
            {
                "departments": [{"value": value, "label": label} for value, label in HondurasDepartment.choices],
                "genders": [{"value": value, "label": label} for value, label in Gender.choices],
                "marital_statuses": [{"value": value, "label": label} for value, label in MaritalStatus.choices],
                "relationships": [{"value": value, "label": label} for value, label in Relationship.choices],
                "branches": [
                    {"id": branch.pk, "name": branch.name, "code": branch.code, "organization_id": branch.organization_id}
                    for branch in branches
                ],
                "organizations": [{"id": org.pk, "name": org.name} for org in organizations],
                "permissions": get_customer_permissions(request.user).as_dict(),
            },
            "Opciones del módulo obtenidas.",
        )


class CustomerRelatedMixin:
    def get_customer(self):
        queryset = scope_customers(Customer.objects.all(), self.request.user)
        return get_object_or_404(queryset, pk=self.kwargs["customer_id"])


class BeneficiaryListCreateView(CustomerRelatedMixin, GenericAPIView):
    permission_classes = (BeneficiaryPermission,)
    serializer_class = BeneficiarySerializer

    def get(self, request, customer_id):
        customer = self.get_customer()
        data = self.get_serializer(customer.beneficiaries.all(), many=True).data
        return success_response(data, "Beneficiarios obtenidos correctamente.")

    def post(self, request, customer_id):
        customer = self.get_customer()
        serializer = self.get_serializer(data=request.data, context={"customer": customer, "request": request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            beneficiary = serializer.save(customer=customer)
            record_activity(customer, request.user, ActivityAction.BENEFICIARY_ADDED)
        return success_response(
            self.get_serializer(beneficiary).data,
            "Beneficiario agregado.",
            status=status.HTTP_201_CREATED,
        )


class BeneficiaryDetailView(CustomerRelatedMixin, GenericAPIView):
    permission_classes = (BeneficiaryPermission,)
    serializer_class = BeneficiarySerializer

    def get_object(self):
        customer = self.get_customer()
        return get_object_or_404(customer.beneficiaries.all(), pk=self.kwargs["pk"])

    def patch(self, request, customer_id, pk):
        beneficiary = self.get_object()
        was_active = beneficiary.is_active
        serializer = self.get_serializer(
            beneficiary,
            data=request.data,
            partial=True,
            context={"customer": beneficiary.customer, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            beneficiary = serializer.save()
            if was_active != beneficiary.is_active:
                action_name = ActivityAction.BENEFICIARY_ACTIVATED if beneficiary.is_active else ActivityAction.BENEFICIARY_DEACTIVATED
            else:
                action_name = ActivityAction.BENEFICIARY_UPDATED
            record_activity(beneficiary.customer, request.user, action_name)
        return success_response(self.get_serializer(beneficiary).data, "Beneficiario actualizado.")


class ContactListCreateView(CustomerRelatedMixin, GenericAPIView):
    permission_classes = (ContactPermission,)
    serializer_class = CustomerContactSerializer

    def get(self, request, customer_id):
        customer = self.get_customer()
        return success_response(
            self.get_serializer(customer.contacts.all(), many=True).data,
            "Contactos obtenidos correctamente.",
        )

    def post(self, request, customer_id):
        customer = self.get_customer()
        serializer = self.get_serializer(data=request.data, context={"customer": customer, "request": request})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            if serializer.validated_data.get("is_primary") and serializer.validated_data.get("is_active", True):
                switch_primary_contact(customer)
            contact = serializer.save(customer=customer)
            record_activity(customer, request.user, ActivityAction.CONTACT_ADDED)
        return success_response(
            self.get_serializer(contact).data,
            "Contacto agregado.",
            status=status.HTTP_201_CREATED,
        )


class ContactDetailView(CustomerRelatedMixin, GenericAPIView):
    permission_classes = (ContactPermission,)
    serializer_class = CustomerContactSerializer

    def get_object(self):
        customer = self.get_customer()
        return get_object_or_404(customer.contacts.all(), pk=self.kwargs["pk"])

    def patch(self, request, customer_id, pk):
        contact = self.get_object()
        was_active = contact.is_active
        serializer = self.get_serializer(contact, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            will_be_primary = serializer.validated_data.get("is_primary", contact.is_primary)
            will_be_active = serializer.validated_data.get("is_active", contact.is_active)
            if will_be_primary and will_be_active:
                switch_primary_contact(contact.customer, contact)
            contact = serializer.save()
            if was_active != contact.is_active:
                action_name = ActivityAction.CONTACT_ACTIVATED if contact.is_active else ActivityAction.CONTACT_DEACTIVATED
            else:
                action_name = ActivityAction.CONTACT_UPDATED
            record_activity(contact.customer, request.user, action_name)
        return success_response(self.get_serializer(contact).data, "Contacto actualizado.")
