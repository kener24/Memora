from dataclasses import dataclass, asdict

from accounts.models import RoleCode


READ_ROLES = {
    RoleCode.ADMIN,
    RoleCode.MANAGER,
    RoleCode.SELLER,
    RoleCode.COLLECTOR,
    RoleCode.CASHIER,
    RoleCode.ACCOUNTANT,
}
CREATE_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SELLER}
EDIT_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SELLER}
MANAGE_RELATED_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.SELLER}
STATUS_ROLES = {RoleCode.ADMIN}
ORGANIZATION_WIDE_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER}


@dataclass(frozen=True)
class CustomerPermissions:
    view: bool = False
    create: bool = False
    edit: bool = False
    change_status: bool = False
    manage_beneficiaries: bool = False
    manage_contacts: bool = False
    global_access: bool = False

    def as_dict(self):
        return asdict(self)


def role_code(user):
    return user.role.code if getattr(user, "role_id", None) else None


def is_global_customer_user(user):
    return bool(user.is_superuser or role_code(user) == RoleCode.SUPERADMIN)


def get_customer_permissions(user):
    if not user or not user.is_authenticated or not user.is_active:
        return CustomerPermissions()
    if is_global_customer_user(user):
        return CustomerPermissions(True, True, True, True, True, True, True)
    code = role_code(user)
    return CustomerPermissions(
        view=code in READ_ROLES,
        create=code in CREATE_ROLES,
        edit=code in EDIT_ROLES,
        change_status=code in STATUS_ROLES,
        manage_beneficiaries=code in MANAGE_RELATED_ROLES,
        manage_contacts=code in MANAGE_RELATED_ROLES,
    )


def is_branch_restricted(user):
    if is_global_customer_user(user):
        return False
    return role_code(user) not in ORGANIZATION_WIDE_ROLES


def scope_customers(queryset, user):
    permissions = get_customer_permissions(user)
    if not permissions.view:
        return queryset.none()
    if permissions.global_access:
        return queryset
    if not user.organization_id:
        return queryset.none()
    queryset = queryset.filter(organization_id=user.organization_id)
    if is_branch_restricted(user):
        if not user.branch_id:
            return queryset.none()
        queryset = queryset.filter(branch_id=user.branch_id)
    return queryset

def scope_branches(queryset, user):
    permissions = get_customer_permissions(user)
    if not permissions.view:
        return queryset.none()
    if permissions.global_access:
        return queryset
    queryset = queryset.filter(organization_id=user.organization_id)
    if is_branch_restricted(user):
        queryset = queryset.filter(pk=user.branch_id) if user.branch_id else queryset.none()
    return queryset
