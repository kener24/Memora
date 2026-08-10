from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from organizations.models import Branch, Organization

from .access import get_customer_permissions, is_branch_restricted, is_global_customer_user
from .choices import Gender, HondurasDepartment, MaritalStatus, Relationship
from .models import Beneficiary, Customer, CustomerActivity, CustomerContact
from .normalization import normalize_email, normalize_identity, normalize_phone, normalize_text


User = get_user_model()


def validate_not_future(value):
    if value and value > date.today():
        raise serializers.ValidationError("La fecha no puede estar en el futuro.")
    return value


class CustomerListSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    branch = serializers.SerializerMethodField()
    department_label = serializers.CharField(source="get_department_display", read_only=True)
    beneficiaries_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Customer
        fields = (
            "id", "customer_code", "full_name", "identity_number", "phone", "email", "branch",
            "department", "department_label", "beneficiaries_count", "is_active", "created_at", "updated_at",
        )

    def get_branch(self, obj):
        if not obj.branch:
            return None
        return {"id": obj.branch_id, "name": obj.branch.name, "code": obj.branch.code}


class BeneficiarySerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    relationship_label = serializers.CharField(source="get_relationship_display", read_only=True)
    age = serializers.SerializerMethodField()
    identity_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    birth_date = serializers.DateField(required=False, allow_null=True, validators=(validate_not_future,))
    phone = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Beneficiary
        fields = (
            "id", "is_customer", "first_name", "middle_name", "last_name", "second_last_name",
            "full_name", "identity_number", "birth_date", "age", "relationship", "relationship_label",
            "phone", "address", "notes", "is_active", "created_at", "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def get_age(self, obj):
        birth_date = obj.customer.birth_date if obj.is_customer else obj.birth_date
        if not birth_date:
            return None
        today = date.today()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    def validate(self, attrs):
        is_customer = attrs.get("is_customer", getattr(self.instance, "is_customer", False))
        relationship = attrs.get("relationship", getattr(self.instance, "relationship", None))
        if is_customer:
            attrs["relationship"] = Relationship.SELF
        elif relationship == Relationship.SELF:
            raise serializers.ValidationError({"is_customer": "Marca al beneficiario como titular."})
        first_name = normalize_text(attrs.get("first_name", getattr(self.instance, "first_name", "")))
        last_name = normalize_text(attrs.get("last_name", getattr(self.instance, "last_name", "")))
        if not is_customer and (not first_name or not last_name):
            raise serializers.ValidationError({"first_name": "Nombre y apellido son obligatorios."})
        customer = self.context.get("customer") or getattr(self.instance, "customer", None)
        active = attrs.get("is_active", getattr(self.instance, "is_active", True))
        if customer and is_customer and active:
            duplicate = customer.beneficiaries.filter(is_customer=True, is_active=True)
            if self.instance:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError({"is_customer": "El titular ya está registrado como beneficiario."})
        return attrs

    def validate_identity_number(self, value):
        try:
            return normalize_identity(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class CustomerContactSerializer(serializers.ModelSerializer):
    phone = serializers.CharField()
    secondary_phone = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = CustomerContact
        fields = (
            "id", "name", "relationship", "phone", "secondary_phone", "notes", "is_primary",
            "is_active", "created_at", "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def validate_name(self, value):
        value = normalize_text(value)
        if not value:
            raise serializers.ValidationError("El nombre es obligatorio.")
        return value

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_secondary_phone(self, value):
        try:
            return normalize_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class CustomerActivitySerializer(serializers.ModelSerializer):
    action_label = serializers.CharField(source="get_action_display", read_only=True)
    user = serializers.SerializerMethodField()

    class Meta:
        model = CustomerActivity
        fields = ("id", "action", "action_label", "description", "user", "created_at")

    def get_user(self, obj):
        if not obj.user:
            return None
        name = obj.user.get_full_name().strip() or obj.user.username
        return {"id": obj.user_id, "name": name}


class CustomerCreateUpdateSerializer(serializers.ModelSerializer):
    organization = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.filter(is_active=True), required=False, write_only=True
    )
    identity_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    birth_date = serializers.DateField(required=False, allow_null=True, validators=(validate_not_future,))
    secondary_phone = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.filter(is_active=True), required=False, allow_null=True
    )

    class Meta:
        model = Customer
        fields = (
            "organization", "branch", "first_name", "middle_name", "last_name", "second_last_name",
            "identity_number", "birth_date", "gender", "marital_status", "phone", "secondary_phone", "email",
            "address", "city", "department", "country", "occupation", "notes",
        )

    def validate_first_name(self, value):
        value = normalize_text(value)
        if not value:
            raise serializers.ValidationError("El nombre es obligatorio.")
        return value

    def validate_last_name(self, value):
        value = normalize_text(value)
        if not value:
            raise serializers.ValidationError("El apellido es obligatorio.")
        return value

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_secondary_phone(self, value):
        try:
            return normalize_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_identity_number(self, value):
        try:
            return normalize_identity(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_email(self, value):
        return normalize_email(value)

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        submitted_org = attrs.get("organization")
        if is_global_customer_user(user):
            organization = submitted_org or user.organization
            if not organization:
                raise serializers.ValidationError({"organization": "Selecciona la organización del cliente."})
        else:
            if not user.organization_id:
                raise serializers.ValidationError({"organization": "Tu usuario no tiene una organización asignada."})
            if submitted_org and submitted_org.pk != user.organization_id:
                raise serializers.ValidationError({"organization": "La organización se determina desde tu sesión."})
            organization = user.organization
            attrs["organization"] = organization

        branch = attrs.get("branch", getattr(self.instance, "branch", None))
        if is_branch_restricted(user):
            if not user.branch_id:
                raise serializers.ValidationError({"branch": "Tu usuario no tiene una sucursal asignada."})
            if branch and branch.pk != user.branch_id:
                raise serializers.ValidationError({"branch": "No puedes seleccionar otra sucursal."})
            attrs["branch"] = user.branch
            branch = user.branch
        if branch and branch.organization_id != organization.id:
            raise serializers.ValidationError({"branch": "La sucursal no pertenece a la organización permitida."})

        identity = attrs.get("identity_number", getattr(self.instance, "identity_number", None))
        active = getattr(self.instance, "is_active", True)
        if identity and active:
            duplicate = Customer.objects.filter(
                organization=organization, identity_number=identity, is_active=True
            )
            if self.instance:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError(
                    {"identity_number": "Ya existe un cliente activo con esta identidad."}
                )

        if self.instance and request.method in {"PATCH", "PUT"}:
            submitted_branch = self.initial_data.get("branch")
            if (
                getattr(user.role, "code", None) == "seller"
                and "branch" in self.initial_data
                and str(submitted_branch or "") != str(self.instance.branch_id or "")
            ):
                raise serializers.ValidationError({"branch": "El rol vendedor no puede cambiar la sucursal."})
        return attrs


class CustomerDetailSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    organization = serializers.SerializerMethodField()
    branch = serializers.SerializerMethodField()
    gender_label = serializers.CharField(source="get_gender_display", read_only=True)
    marital_status_label = serializers.CharField(source="get_marital_status_display", read_only=True)
    department_label = serializers.CharField(source="get_department_display", read_only=True)
    created_by = serializers.SerializerMethodField()
    beneficiaries = BeneficiarySerializer(many=True, read_only=True)
    contacts = CustomerContactSerializer(many=True, read_only=True)
    activities = CustomerActivitySerializer(many=True, read_only=True)
    financial_summary = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = (
            "id", "customer_code", "full_name", "first_name", "middle_name", "last_name", "second_last_name",
            "identity_number", "birth_date", "gender", "gender_label", "marital_status", "marital_status_label",
            "phone", "secondary_phone", "email", "address", "city", "department", "department_label", "country",
            "occupation", "notes", "organization", "branch", "is_active", "created_by", "created_at", "updated_at",
            "beneficiaries", "contacts", "activities", "financial_summary",
        )

    def get_financial_summary(self, obj):
        from payments.services import customer_financial_summary

        return customer_financial_summary(obj)

    def get_organization(self, obj):
        return {"id": obj.organization_id, "name": obj.organization.name}

    def get_branch(self, obj):
        if not obj.branch:
            return None
        return {"id": obj.branch_id, "name": obj.branch.name, "code": obj.branch.code}

    def get_created_by(self, obj):
        name = obj.created_by.get_full_name().strip() or obj.created_by.username
        return {"id": obj.created_by_id, "name": name}


class DuplicateCheckSerializer(serializers.Serializer):
    identity_number = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)

    def validate_identity_number(self, value):
        try:
            return normalize_identity(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def validate_phone(self, value):
        try:
            return normalize_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
