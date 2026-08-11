from rest_framework.permissions import BasePermission

from .access import get_cash_permissions


class CashPermission(BasePermission):
    def has_permission(self, request, view):
        permissions = get_cash_permissions(request.user)
        action = getattr(view, "action", None)
        required = {
            "list": "view_session", "retrieve": "view_session",
            "create": "create_income", "void": "void_movement",
            "open": "open_session", "close": "close_session",
            "count": "perform_cash_count", "pending": "receive_collector_settlement",
        }.get(action, "view_session")
        return bool(request.user and request.user.is_authenticated and getattr(permissions, required))
