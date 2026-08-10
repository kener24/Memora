from dataclasses import asdict, dataclass

from django.db.models import Q

from accounts.models import RoleCode


READ_ROLES = {
    RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SELLER, RoleCode.COLLECTOR,
    RoleCode.CASHIER, RoleCode.INVENTORY, RoleCode.ACCOUNTANT,
}
MANAGE_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER}
STATUS_ROLES = {RoleCode.ADMIN}
COST_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.ACCOUNTANT}
ORGANIZATION_WIDE_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.ACCOUNTANT}


@dataclass(frozen=True)
class PlanPermissions:
    view: bool = False
    create: bool = False
    edit: bool = False
    change_status: bool = False
    duplicate: bool = False
    manage_services: bool = False
    view_costs: bool = False
    global_access: bool = False

    def as_dict(self):
        return asdict(self)


def role_code(user):
    return user.role.code if getattr(user, "role_id", None) else None


def is_global_plan_user(user):
    return bool(user.is_superuser or role_code(user) == RoleCode.SUPERADMIN)


def get_plan_permissions(user):
    if not user or not user.is_authenticated or not user.is_active:
        return PlanPermissions()
    if is_global_plan_user(user):
        return PlanPermissions(True, True, True, True, True, True, True, True)
    code = role_code(user)
    can_manage = code in MANAGE_ROLES
    return PlanPermissions(
        view=code in READ_ROLES,
        create=can_manage,
        edit=can_manage,
        change_status=code in STATUS_ROLES,
        duplicate=can_manage,
        manage_services=can_manage,
        view_costs=code in COST_ROLES,
    )


def scope_plans(queryset, user):
    permissions = get_plan_permissions(user)
    if not permissions.view:
        return queryset.none()
    if permissions.global_access:
        return queryset
    if not user.organization_id:
        return queryset.none()
    queryset = queryset.filter(organization_id=user.organization_id)
    if role_code(user) not in ORGANIZATION_WIDE_ROLES:
        if not user.branch_id:
            return queryset.none()
        queryset = queryset.filter(
            Q(available_all_branches=True) | Q(branch_availabilities__branch_id=user.branch_id),
            is_active=True,
        ).distinct()
    return queryset


def scope_services(queryset, user):
    permissions = get_plan_permissions(user)
    if not permissions.view:
        return queryset.none()
    if permissions.global_access:
        return queryset
    if not user.organization_id:
        return queryset.none()
    queryset = queryset.filter(organization_id=user.organization_id)
    if not permissions.manage_services and role_code(user) != RoleCode.ACCOUNTANT:
        queryset = queryset.filter(is_active=True)
    return queryset
