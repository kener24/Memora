from rest_framework.permissions import BasePermission

from .access import get_contract_permissions


class ContractPermission(BasePermission):
    message = "No tiene permisos para acceder al módulo de contratos."

    def has_permission(self, request, view):
        permissions = get_contract_permissions(request.user)
        action = getattr(view, "action", None)
        if request.method == "GET":
            return permissions.view
        if action in {"create", "confirm"}:
            return permissions.create
        if action == "cancel":
            return permissions.cancel
        if request.method in {"PATCH", "PUT"}:
            return permissions.edit_draft
        return False
