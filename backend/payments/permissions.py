from rest_framework.permissions import BasePermission

from .access import get_payment_permissions


class PaymentPermission(BasePermission):
    def has_permission(self, request, view):
        permissions = get_payment_permissions(request.user)
        if view.action in {"list", "retrieve", "receipt", "receipt_pdf"}:
            return permissions.view_payment
        if view.action == "create":
            return permissions.create_payment
        if view.action == "void":
            return permissions.void_payment
        return False
