from dataclasses import asdict, dataclass

from accounts.models import RoleCode
from contracts.access import is_branch_restricted, is_global_contract_user


VIEW_ROLES = {
    RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SELLER, RoleCode.COLLECTOR,
    RoleCode.CASHIER, RoleCode.ACCOUNTANT,
}
MANAGE_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER}


@dataclass(frozen=True)
class InstallmentPermissions:
    view_installments: bool = False
    generate_schedule: bool = False
    reprogram_schedule: bool = False
    view_costs: bool = False
    global_access: bool = False

    def as_dict(self):
        return asdict(self)


def role_code(user):
    return user.role.code if getattr(user, "role_id", None) else None


def get_installment_permissions(user):
    if not user or not user.is_authenticated or not user.is_active:
        return InstallmentPermissions()
    if is_global_contract_user(user):
        return InstallmentPermissions(True, True, True, True, True)
    code = role_code(user)
    return InstallmentPermissions(
        view_installments=code in VIEW_ROLES,
        generate_schedule=code in MANAGE_ROLES,
        reprogram_schedule=code in MANAGE_ROLES,
        view_costs=code in {RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.ACCOUNTANT},
    )


def scope_installments(queryset, user):
    permissions = get_installment_permissions(user)
    if not permissions.view_installments:
        return queryset.none()
    if permissions.global_access:
        return queryset
    if not user.organization_id:
        return queryset.none()
    queryset = queryset.filter(organization_id=user.organization_id)
    if is_branch_restricted(user):
        return queryset.filter(branch_id=user.branch_id) if user.branch_id else queryset.none()
    return queryset


def scope_schedules(queryset, user):
    permissions = get_installment_permissions(user)
    if not permissions.view_installments:
        return queryset.none()
    if permissions.global_access:
        return queryset
    if not user.organization_id:
        return queryset.none()
    queryset = queryset.filter(organization_id=user.organization_id)
    if is_branch_restricted(user):
        return queryset.filter(branch_id=user.branch_id) if user.branch_id else queryset.none()
    return queryset
