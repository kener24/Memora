from django.contrib.auth import authenticate, get_user_model
from django.db.models import Q
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken


User = get_user_model()


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254, trim_whitespace=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    default_error_messages = {
        "invalid_credentials": "El correo, usuario o contraseña no son válidos.",
    }

    def validate(self, attrs):
        identifier = attrs["identifier"].strip()
        password = attrs["password"]
        user_record = User.objects.filter(
            Q(username__iexact=identifier) | Q(email__iexact=identifier)
        ).first()

        user = None
        if user_record is not None:
            user = authenticate(
                request=self.context.get("request"),
                username=user_record.username,
                password=password,
            )

        if user is None or not user.is_active:
            self.fail("invalid_credentials")

        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }


class UserMeSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="first_name")
    apellido = serializers.CharField(source="last_name")
    rol = serializers.SerializerMethodField()
    organizacion = serializers.SerializerMethodField()
    sucursal = serializers.SerializerMethodField()
    permisos = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "nombre", "apellido", "email", "rol", "organizacion", "sucursal", "permisos")

    def get_rol(self, obj):
        if not obj.role:
            return None
        return {"codigo": obj.role.code, "nombre": obj.role.name}

    def get_organizacion(self, obj):
        if not obj.organization:
            return None
        return {"id": obj.organization_id, "nombre": obj.organization.name}

    def get_sucursal(self, obj):
        if not obj.branch:
            return None
        return {"id": obj.branch_id, "nombre": obj.branch.name, "codigo": obj.branch.code}

    def get_permisos(self, obj):
        from customers.access import get_customer_permissions
        from plans.access import get_plan_permissions
        from contracts.access import get_contract_permissions
        from installments.access import get_installment_permissions
        from payments.access import get_payment_permissions
        from collection_management.access import get_collection_permissions
        from cash.access import get_cash_permissions

        return {
            "es_staff": obj.is_staff,
            "es_superusuario": obj.is_superuser,
            "acceso_admin": obj.is_staff and obj.is_active,
            "clientes": get_customer_permissions(obj).as_dict(),
            "planes": get_plan_permissions(obj).as_dict(),
            "contratos": get_contract_permissions(obj).as_dict(),
            "cuotas": get_installment_permissions(obj).as_dict(),
            "pagos": get_payment_permissions(obj).as_dict(),
            "cobranza": get_collection_permissions(obj).as_dict(),
            "caja": get_cash_permissions(obj).as_dict(),
        }
