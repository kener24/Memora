from dataclasses import asdict, dataclass

from accounts.models import RoleCode


READ_ROLES = {
    RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SELLER, RoleCode.COLLECTOR,
    RoleCode.CASHIER, RoleCode.ACCOUNTANT,
}
CREATE_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SELLER}
CANCEL_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER}
DISCOUNT_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER}
COST_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.ACCOUNTANT}
ORGANIZATION_WIDE_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.ACCOUNTANT}


@dataclass(frozen=True)
class ContractPermissions:
    view: bool = False
    create: bool = False
    edit_draft: bool = False
    cancel: bool = False
    apply_discount: bool = False
    view_costs: bool = False
    global_access: bool = False

    def as_dict(self):
        return asdict(self)


def role_code(user):
    return user.role.code if getattr(user, "role_id", None) else None


def is_global_contract_user(user):
    return bool(user.is_superuser or role_code(user) == RoleCode.SUPERADMIN)


def get_contract_permissions(user):
    if not user or not user.is_authenticated or not user.is_active:
        return ContractPermissions()
    if is_global_contract_user(user):
        return ContractPermissions(True, True, True, True, True, True, True)
    code = role_code(user)
    return ContractPermissions(
        view=code in READ_ROLES,
        create=code in CREATE_ROLES,
        edit_draft=code in CREATE_ROLES,
        cancel=code in CANCEL_ROLES,
        apply_discount=code in DISCOUNT_ROLES,
        view_costs=code in COST_ROLES,
    )


def is_branch_restricted(user):
    return not is_global_contract_user(user) and role_code(user) not in ORGANIZATION_WIDE_ROLES


def scope_contracts(queryset, user):
    permissions = get_contract_permissions(user)
    if not permissions.view:
        return queryset.none()
    if permissions.global_access:
        return queryset
    if not user.organization_id:
        return queryset.none()
    queryset = queryset.filter(organization_id=user.organization_id)
    if is_branch_restricted(user):
        queryset = queryset.filter(branch_id=user.branch_id) if user.branch_id else queryset.none()
    return queryset
