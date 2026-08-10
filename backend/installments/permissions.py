from rest_framework.permissions import BasePermission

from .access import get_installment_permissions


class InstallmentPermission(BasePermission):
    message = "No tiene permisos para acceder al módulo de cuotas."

    def has_permission(self, request, view):
        return get_installment_permissions(request.user).view_installments
