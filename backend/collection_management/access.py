from dataclasses import asdict, dataclass

from accounts.models import RoleCode
from contracts.access import is_branch_restricted, is_global_contract_user


VIEW_ROLES = {
    RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.COLLECTOR, RoleCode.CASHIER,
    RoleCode.SELLER, RoleCode.ACCOUNTANT,
}
ACTION_CREATE_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.COLLECTOR}
VOID_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER}
PROMISE_CREATE_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.COLLECTOR}
PROMISE_RESOLVE_ROLES = {RoleCode.ADMIN, RoleCode.MANAGER}


@dataclass(frozen=True)
class CollectionPermissions:
    view_portfolio: bool = False
    view_overdue: bool = False
    create_action: bool = False
    view_action: bool = False
    void_action: bool = False
    create_promise: bool = False
    view_promise: bool = False
    resolve_promise: bool = False
    export_portfolio: bool = False
    global_access: bool = False
    manage_collectors: bool = False
    assign_portfolio: bool = False
    reassign_portfolio: bool = False
    manage_zones: bool = False
    manage_routes: bool = False
    view_own_portfolio: bool = False
    view_collector_metrics: bool = False
    start_work_session: bool = False
    close_work_session: bool = False
    submit_settlement: bool = False
    review_settlement: bool = False
    accept_settlement: bool = False
    reject_settlement: bool = False
    view_settlement: bool = False
    export_collections: bool = False

    def as_dict(self):
        return asdict(self)


def role_code(user):
    return user.role.code if getattr(user, "role_id", None) else None


def get_collection_permissions(user):
    if not user or not user.is_authenticated or not user.is_active:
        return CollectionPermissions()
    if is_global_contract_user(user):
        return CollectionPermissions(**{field: True for field in CollectionPermissions.__dataclass_fields__})
    code = role_code(user)
    can_view = code in VIEW_ROLES
    manages = code in {RoleCode.ADMIN, RoleCode.MANAGER}
    collector = code == RoleCode.COLLECTOR
    return CollectionPermissions(
        view_portfolio=can_view,
        view_overdue=can_view,
        create_action=code in ACTION_CREATE_ROLES,
        view_action=can_view,
        void_action=code in VOID_ROLES,
        create_promise=code in PROMISE_CREATE_ROLES,
        view_promise=can_view,
        resolve_promise=code in PROMISE_RESOLVE_ROLES,
        export_portfolio=code in {RoleCode.ADMIN, RoleCode.MANAGER, RoleCode.ACCOUNTANT},
        manage_collectors=manages,
        assign_portfolio=manages,
        reassign_portfolio=manages,
        manage_zones=manages,
        manage_routes=manages,
        view_own_portfolio=collector,
        view_collector_metrics=manages or code == RoleCode.ACCOUNTANT or collector,
        start_work_session=collector or manages,
        close_work_session=collector or manages,
        submit_settlement=collector,
        review_settlement=manages,
        accept_settlement=manages,
        reject_settlement=manages,
        view_settlement=collector or manages or code in {RoleCode.CASHIER, RoleCode.ACCOUNTANT},
        export_collections=manages or code == RoleCode.ACCOUNTANT,
    )


def _scope(queryset, user, permission):
    permissions = get_collection_permissions(user)
    if not getattr(permissions, permission):
        return queryset.none()
    if permissions.global_access:
        return queryset
    if not user.organization_id:
        return queryset.none()
    queryset = queryset.filter(organization_id=user.organization_id)
    if is_branch_restricted(user):
        return queryset.filter(branch_id=user.branch_id) if user.branch_id else queryset.none()
    return queryset


def scope_actions(queryset, user):
    return _scope(queryset, user, "view_action")


def scope_promises(queryset, user):
    return _scope(queryset, user, "view_promise")


def scope_operations(queryset, user, permission="view_collector_metrics", *, branch_field="branch"):
    permissions = get_collection_permissions(user)
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


def scope_settlements(queryset, user):
    permissions = get_collection_permissions(user)
    if not permissions.view_settlement:
        return queryset.none()
    if permissions.global_access:
        return queryset
    queryset = queryset.filter(organization_id=user.organization_id)
    if role_code(user) == RoleCode.COLLECTOR:
        return queryset.filter(collector=user)
    if is_branch_restricted(user):
        return queryset.filter(branch_id=user.branch_id) if user.branch_id else queryset.none()
    return queryset
