from dataclasses import asdict, dataclass

from accounts.models import RoleCode
from contracts.access import is_branch_restricted, is_global_contract_user


@dataclass(frozen=True)
class CashPermissions:
    view_cash_register: bool = False
    manage_cash_register: bool = False
    open_session: bool = False
    view_session: bool = False
    close_session: bool = False
    create_income: bool = False
    create_expense: bool = False
    void_movement: bool = False
    receive_collector_settlement: bool = False
    perform_cash_count: bool = False
    view_cash_history: bool = False
    export_cash: bool = False
    global_access: bool = False

    def as_dict(self):
        return asdict(self)


def role_code(user):
    return user.role.code if getattr(user, "role_id", None) else None


def get_cash_permissions(user):
    if not user or not user.is_authenticated or not user.is_active:
        return CashPermissions()
    if is_global_contract_user(user):
        return CashPermissions(**{field: True for field in CashPermissions.__dataclass_fields__})
    code = role_code(user)
    manages = code in {RoleCode.ADMIN, RoleCode.MANAGER}
    cashier = code == RoleCode.CASHIER
    accountant = code == RoleCode.ACCOUNTANT
    can_operate = manages or cashier
    can_view = can_operate or accountant
    return CashPermissions(
        view_cash_register=can_view,
        manage_cash_register=manages,
        open_session=can_operate,
        view_session=can_view,
        close_session=can_operate,
        create_income=can_operate,
        create_expense=can_operate,
        void_movement=can_operate,
        receive_collector_settlement=can_operate,
        perform_cash_count=can_operate,
        view_cash_history=can_view,
        export_cash=manages or accountant,
        global_access=False,
    )


def scope_cash(queryset, user, permission="view_session", *, branch_field="branch"):
    permissions = get_cash_permissions(user)
    if not getattr(permissions, permission):
        return queryset.none()
    if permissions.global_access:
        return queryset
    if not user.organization_id:
        return queryset.none()
    queryset = queryset.filter(organization_id=user.organization_id)
    if is_branch_restricted(user):
        return queryset.filter(**{f"{branch_field}_id": user.branch_id}) if user.branch_id else queryset.none()
    return queryset
