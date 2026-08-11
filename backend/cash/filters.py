from django.utils import timezone
from django.utils.dateparse import parse_date

from .choices import CashMovementDirection, CashMovementStatus, CashMovementType, CashSessionStatus


def filter_movements(queryset, params):
    for parameter, lookup in (
        ("session", "cash_session_id"), ("register", "cash_session__cash_register_id"),
        ("branch", "branch_id"), ("user", "created_by_id"),
    ):
        if params.get(parameter):
            queryset = queryset.filter(**{lookup: params[parameter]})
    if params.get("direction") in CashMovementDirection.values:
        queryset = queryset.filter(direction=params["direction"])
    if params.get("movement_type") in CashMovementType.values:
        queryset = queryset.filter(movement_type=params["movement_type"])
    if params.get("status") in CashMovementStatus.values:
        queryset = queryset.filter(status=params["status"])
    if params.get("payment_method"):
        queryset = queryset.filter(payment_method=params["payment_method"])
    date_from = parse_date(params.get("date_from", ""))
    date_to = parse_date(params.get("date_to", ""))
    if params.get("preset") == "today":
        date_from = date_to = timezone.localdate()
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)
    return queryset


def filter_sessions(queryset, params):
    if params.get("status") in CashSessionStatus.values:
        queryset = queryset.filter(status=params["status"])
    for parameter, lookup in (
        ("register", "cash_register_id"), ("branch", "branch_id"), ("cashier", "cashier_id"),
    ):
        if params.get(parameter):
            queryset = queryset.filter(**{lookup: params[parameter]})
    date_from = parse_date(params.get("date_from", ""))
    date_to = parse_date(params.get("date_to", ""))
    if date_from:
        queryset = queryset.filter(opened_at__date__gte=date_from)
    if date_to:
        queryset = queryset.filter(opened_at__date__lte=date_to)
    return queryset
