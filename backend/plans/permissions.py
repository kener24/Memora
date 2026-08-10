from rest_framework.permissions import BasePermission

from .access import get_plan_permissions


class PlanPermission(BasePermission):
    message = "No tiene permisos para acceder al módulo de planes."

    def has_permission(self, request, view):
        permissions = get_plan_permissions(request.user)
        action = getattr(view, "action", None)
        if request.method == "GET":
            return permissions.view
        if action == "create":
            return permissions.create
        if action in {"activate", "deactivate"}:
            return permissions.change_status
        if action == "duplicate":
            return permissions.duplicate
        if request.method in {"PATCH", "PUT"}:
            return permissions.edit
        return False


class ServicePermission(BasePermission):
    message = "No tiene permisos para gestionar el catálogo de servicios."

    def has_permission(self, request, view):
        permissions = get_plan_permissions(request.user)
        action = getattr(view, "action", None)
        if request.method == "GET":
            return permissions.view
        if action in {"activate", "deactivate"}:
            return permissions.change_status
        return permissions.manage_services
