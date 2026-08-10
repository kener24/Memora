from rest_framework.permissions import BasePermission

from .access import get_customer_permissions


class CustomerPermission(BasePermission):
    message = "No tiene permisos para acceder al módulo de clientes."

    def has_permission(self, request, view):
        permissions = get_customer_permissions(request.user)
        action = getattr(view, "action", None)
        if request.method == "GET":
            return permissions.view
        if action == "create" or action == "check_duplicates":
            return permissions.create
        if action in {"activate", "deactivate"}:
            return permissions.change_status
        if request.method in {"PATCH", "PUT"}:
            return permissions.edit
        return False


class CustomerRelatedPermission(BasePermission):
    message = "No tiene permisos para gestionar esta información del cliente."
    permission_name = None

    def has_permission(self, request, view):
        permissions = get_customer_permissions(request.user)
        if request.method == "GET":
            return permissions.view
        return bool(getattr(permissions, self.permission_name, False))


class BeneficiaryPermission(CustomerRelatedPermission):
    permission_name = "manage_beneficiaries"


class ContactPermission(CustomerRelatedPermission):
    permission_name = "manage_contacts"
