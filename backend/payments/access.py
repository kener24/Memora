from dataclasses import asdict, dataclass

from accounts.models import RoleCode
from contracts.access import is_branch_restricted, is_global_contract_user


VIEW_ROLES = {
    RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.CASHIER, RoleCode.COLLECTOR,
    RoleCode.SELLER, RoleCode.ACCOUNTANT,
}
CREATE_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.CASHIER, RoleCode.COLLECTOR}
VOID_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER}
INITIAL_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.CASHIER}
SETTLE_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER}
BACKDATE_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER}


@dataclass(frozen=True)
class PaymentPermissions:
    view_payment: bool = False
    create_payment: bool = False
    void_payment: bool = False
    register_initial_payment: bool = False
    settle_contract: bool = False
    view_receipt: bool = False
    backdate_payment: bool = False
    global_access: bool = False

    def as_dict(self):
        return asdict(self)


def role_code(user):
    return user.role.code if getattr(user, "role_id", None) else None


def get_payment_permissions(user):
    if not user or not user.is_authenticated or not user.is_active:
        return PaymentPermissions()
    if is_global_contract_user(user):
        return PaymentPermissions(True, True, True, True, True, True, True, True)
    code = role_code(user)
    return PaymentPermissions(
        view_payment=code in VIEW_ROLES,
        create_payment=code in CREATE_ROLES,
        void_payment=code in VOID_ROLES,
        register_initial_payment=code in INITIAL_ROLES,
        settle_contract=code in SETTLE_ROLES,
        view_receipt=code in VIEW_ROLES,
        backdate_payment=code in BACKDATE_ROLES,
    )


def scope_payments(queryset, user):
    permissions = get_payment_permissions(user)
    if not permissions.view_payment:
        return queryset.none()
    if permissions.global_access:
        return queryset
    if not user.organization_id:
        return queryset.none()
    queryset = queryset.filter(organization_id=user.organization_id)
    if is_branch_restricted(user):
        return queryset.filter(branch_id=user.branch_id) if user.branch_id else queryset.none()
    return queryset


def scope_receipts(queryset, user):
    permissions = get_payment_permissions(user)
    if not permissions.view_receipt:
        return queryset.none()
    if permissions.global_access:
        return queryset
    if not user.organization_id:
        return queryset.none()
    queryset = queryset.filter(organization_id=user.organization_id)
    if is_branch_restricted(user):
        return queryset.filter(branch_id=user.branch_id) if user.branch_id else queryset.none()
    return queryset
