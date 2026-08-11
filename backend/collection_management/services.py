from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import (
    Case, Count, DateTimeField, DecimalField, ExpressionWrapper, F, IntegerField, Max, Min,
    OuterRef, Q, Subquery, Sum, Value, When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import RoleCode
from contracts.access import scope_contracts
from contracts.choices import ContractStatus
from contracts.exceptions import ConflictError
from contracts.models import Contract
from installments.choices import InstallmentStatus, ScheduleStatus
from installments.models import Installment
from payments.access import scope_payments
from payments.choices import PaymentStatus
from payments.models import Payment
from payments.services import money

from .access import scope_actions, scope_promises
from .choices import (
    AGING_BUCKETS, DUE_SOON_DAYS, PROMISE_PAYMENT_GRACE_DAYS, RECENT_PAYMENT_DAYS, AssignmentStatus,
    SEVERE_OVERDUE_DAYS, AuditEvent, CollectionActionStatus, CollectionOutcome,
    CollectionPriority, CollectionStatus, PromiseStatus,
)
from .models import CollectionAction, CollectionAudit, PaymentPromise


ZERO = Decimal("0.00")
MONEY_FIELD = DecimalField(max_digits=14, decimal_places=2)


def _payment_totals():
    return Payment.objects.filter(
        contract=OuterRef("pk"), status=PaymentStatus.CONFIRMED
    ).values("contract").annotate(
        total=Sum("amount"), initial=Sum("initial_amount_applied"), latest=Max("payment_date")
    )


def _active_installment_stats(today):
    pending = ExpressionWrapper(F("current_amount") - F("paid_amount"), output_field=MONEY_FIELD)
    payable = Q(current_amount__gt=F("paid_amount")) & ~Q(status=InstallmentStatus.CANCELLED)
    return Installment.objects.filter(
        contract=OuterRef("pk"), schedule__status=ScheduleStatus.ACTIVE,
    ).values("contract").annotate(
        scheduled_pending=Sum(pending, filter=payable),
        overdue_amount=Sum(pending, filter=payable & Q(due_date__lt=today)),
        overdue_count=Count("id", filter=payable & Q(due_date__lt=today)),
        oldest_overdue=Min("due_date", filter=payable & Q(due_date__lt=today)),
        next_due=Min("due_date", filter=payable & Q(due_date__gte=today)),
    )


def portfolio_queryset(user, *, include_paid=False, today=None):
    today = today or timezone.localdate()
    payments = _payment_totals()
    installments = _active_installment_stats(today)
    last_payment = Payment.objects.filter(
        contract=OuterRef("pk"), status=PaymentStatus.CONFIRMED
    ).order_by("-payment_date", "-created_at", "-id")
    last_action = CollectionAction.objects.filter(
        contract=OuterRef("pk"), status=CollectionActionStatus.ACTIVE
    ).order_by("-contact_date", "-id")
    active_promise = PaymentPromise.objects.filter(
        contract=OuterRef("pk"), status=PromiseStatus.PENDING
    ).order_by("promised_date", "id")
    queryset = scope_contracts(
        Contract.objects.filter(status=ContractStatus.ACTIVE).select_related(
            "customer", "branch", "plan", "seller",
        ), user,
    ).annotate(
        total_paid_calc=Coalesce(Subquery(payments.values("total")[:1]), Value(ZERO), output_field=MONEY_FIELD),
        initial_paid_calc=Coalesce(Subquery(payments.values("initial")[:1]), Value(ZERO), output_field=MONEY_FIELD),
        scheduled_pending_calc=Coalesce(
            Subquery(installments.values("scheduled_pending")[:1]), Value(ZERO), output_field=MONEY_FIELD,
        ),
        overdue_amount_calc=Coalesce(
            Subquery(installments.values("overdue_amount")[:1]), Value(ZERO), output_field=MONEY_FIELD,
        ),
        overdue_count_calc=Coalesce(
            Subquery(installments.values("overdue_count")[:1]), Value(0), output_field=IntegerField(),
        ),
        oldest_overdue_date=Subquery(installments.values("oldest_overdue")[:1]),
        next_due_date=Subquery(installments.values("next_due")[:1]),
        last_payment_date=Subquery(last_payment.values("payment_date")[:1]),
        last_payment_amount=Subquery(last_payment.values("amount")[:1]),
        last_payment_number=Subquery(last_payment.values("payment_number")[:1]),
        last_action_date=Subquery(last_action.values("contact_date")[:1]),
        last_action_outcome=Subquery(last_action.values("outcome")[:1]),
        pending_promise_date=Subquery(active_promise.values("promised_date")[:1]),
        pending_promise_amount=Subquery(active_promise.values("promised_amount")[:1]),
    ).annotate(
        balance_calc=ExpressionWrapper(F("total_price") - F("total_paid_calc"), output_field=MONEY_FIELD),
        initial_pending_calc=ExpressionWrapper(
            F("initial_payment_agreed") - F("initial_paid_calc"), output_field=MONEY_FIELD,
        ),
    ).annotate(
        upcoming_amount_calc=ExpressionWrapper(F("balance_calc") - F("overdue_amount_calc"), output_field=MONEY_FIELD),
    )
    if not include_paid:
        queryset = queryset.filter(balance_calc__gt=0)
    if getattr(getattr(user, "role", None), "code", None) == RoleCode.COLLECTOR:
        queryset = queryset.filter(
            collection_assignments__collector=user, collection_assignments__status=AssignmentStatus.ACTIVE,
        )
    return queryset


def _date_for_min_days(today, minimum):
    return today - timedelta(days=minimum)


def _date_for_max_days(today, maximum):
    return today - timedelta(days=maximum + 1)


def apply_portfolio_filters(queryset, params, *, today=None):
    today = today or timezone.localdate()
    search = (params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(contract_number__icontains=search) | Q(customer_name_snapshot__icontains=search)
            | Q(customer_identity_snapshot__icontains=search) | Q(customer_phone_snapshot__icontains=search)
            | Q(customer__customer_code__icontains=search) | Q(customer__first_name__icontains=search)
            | Q(customer__last_name__icontains=search)
        )
    for parameter, lookup in (("branch", "branch_id"), ("seller", "seller_id"), ("plan", "plan_id")):
        if params.get(parameter):
            queryset = queryset.filter(**{lookup: params[parameter]})
    if params.get("collector"):
        queryset = queryset.filter(
            collection_assignments__collector_id=params["collector"],
            collection_assignments__status=AssignmentStatus.ACTIVE,
        )
    if params.get("assignment") == "unassigned":
        queryset = queryset.exclude(collection_assignments__status=AssignmentStatus.ACTIVE)
    elif params.get("assignment") == "assigned":
        queryset = queryset.filter(collection_assignments__status=AssignmentStatus.ACTIVE)
    if params.get("zone") == "none":
        queryset = queryset.filter(customer__collection_zone_link__isnull=True)
    elif params.get("zone"):
        queryset = queryset.filter(customer__collection_zone_link__zone_id=params["zone"])
    try:
        if params.get("balance_min"):
            queryset = queryset.filter(balance_calc__gte=money(params["balance_min"]))
        if params.get("balance_max"):
            queryset = queryset.filter(balance_calc__lte=money(params["balance_max"]))
        if params.get("days_min"):
            queryset = queryset.filter(oldest_overdue_date__lte=_date_for_min_days(today, int(params["days_min"])))
        if params.get("days_max"):
            queryset = queryset.filter(oldest_overdue_date__gt=_date_for_max_days(today, int(params["days_max"])))
    except (TypeError, ValueError):
        raise ValidationError({"filters": "Los rangos numéricos no son válidos."})

    status = params.get("status")
    if status == CollectionStatus.PAID:
        queryset = queryset.filter(balance_calc=0)
    elif status == CollectionStatus.SEVERELY_OVERDUE:
        queryset = queryset.filter(oldest_overdue_date__lt=today - timedelta(days=SEVERE_OVERDUE_DAYS))
    elif status == CollectionStatus.OVERDUE:
        queryset = queryset.filter(
            overdue_amount_calc__gt=0,
            oldest_overdue_date__gte=today - timedelta(days=SEVERE_OVERDUE_DAYS),
        )
    elif status == CollectionStatus.DUE_SOON:
        queryset = queryset.filter(
            overdue_amount_calc=0, next_due_date__gte=today,
            next_due_date__lte=today + timedelta(days=DUE_SOON_DAYS), balance_calc__gt=0,
        )
    elif status == CollectionStatus.CURRENT:
        queryset = queryset.filter(overdue_amount_calc=0, balance_calc__gt=0).filter(
            Q(next_due_date__isnull=True) | Q(next_due_date__gt=today + timedelta(days=DUE_SOON_DAYS))
        )

    preset = params.get("preset")
    if preset == "due_today":
        queryset = queryset.filter(next_due_date=today, overdue_amount_calc=0)
    elif preset == "next_7_days":
        queryset = queryset.filter(
            next_due_date__gte=today, next_due_date__lte=today + timedelta(days=DUE_SOON_DAYS),
            overdue_amount_calc=0,
        )
    elif preset == "over_90":
        queryset = queryset.filter(oldest_overdue_date__lt=today - timedelta(days=90))
    elif preset == "no_recent_payment":
        queryset = queryset.filter(Q(last_payment_date__isnull=True) | Q(
            last_payment_date__lt=timezone.now() - timedelta(days=RECENT_PAYMENT_DAYS)
        ))
    elif preset in {item[0] for item in AGING_BUCKETS}:
        _, _, minimum, maximum = next(item for item in AGING_BUCKETS if item[0] == preset)
        queryset = queryset.filter(oldest_overdue_date__lte=_date_for_min_days(today, minimum))
        if maximum is not None:
            queryset = queryset.filter(oldest_overdue_date__gt=_date_for_max_days(today, maximum))

    recent = params.get("recent_payment")
    recent_limit = timezone.now() - timedelta(days=RECENT_PAYMENT_DAYS)
    if recent == "yes":
        queryset = queryset.filter(last_payment_date__gte=recent_limit)
    elif recent == "no":
        queryset = queryset.filter(Q(last_payment_date__lt=recent_limit) | Q(last_payment_date__isnull=True))

    ordering = {
        "balance": ("balance_calc", "customer_name_snapshot"),
        "-balance": ("-balance_calc", "customer_name_snapshot"),
        "overdue": ("overdue_amount_calc", "customer_name_snapshot"),
        "-overdue": ("-overdue_amount_calc", "oldest_overdue_date"),
        "days_overdue": ("-oldest_overdue_date", "customer_name_snapshot"),
        "-days_overdue": ("oldest_overdue_date", "-overdue_amount_calc"),
        "next_due": ("next_due_date", "customer_name_snapshot"),
        "-next_due": ("-next_due_date", "customer_name_snapshot"),
        "last_payment": ("last_payment_date", "customer_name_snapshot"),
        "-last_payment": ("-last_payment_date", "customer_name_snapshot"),
        "customer": ("customer_name_snapshot", "contract_number"),
        "-customer": ("-customer_name_snapshot", "contract_number"),
    }.get(params.get("ordering"), ("oldest_overdue_date", "-overdue_amount_calc", "customer_name_snapshot"))
    return queryset.order_by(*ordering)


def collection_status(contract, *, today=None):
    today = today or timezone.localdate()
    if contract.balance_calc <= 0:
        return CollectionStatus.PAID
    if contract.overdue_amount_calc > 0 and contract.oldest_overdue_date:
        if (today - contract.oldest_overdue_date).days > SEVERE_OVERDUE_DAYS:
            return CollectionStatus.SEVERELY_OVERDUE
        return CollectionStatus.OVERDUE
    if contract.next_due_date and today <= contract.next_due_date <= today + timedelta(days=DUE_SOON_DAYS):
        return CollectionStatus.DUE_SOON
    return CollectionStatus.CURRENT


def collection_priority(contract, *, today=None):
    today = today or timezone.localdate()
    if contract.pending_promise_date and contract.pending_promise_date < today:
        return CollectionPriority.CRITICAL
    days = (today - contract.oldest_overdue_date).days if contract.oldest_overdue_date else 0
    if days > SEVERE_OVERDUE_DAYS:
        return CollectionPriority.CRITICAL
    if days > 30:
        return CollectionPriority.HIGH
    if days > 0:
        return CollectionPriority.MEDIUM
    return CollectionPriority.LOW


def portfolio_row(contract, *, today=None):
    today = today or timezone.localdate()
    status = collection_status(contract, today=today)
    priority = collection_priority(contract, today=today)
    return {
        "contract_id": contract.pk, "contract_number": contract.contract_number,
        "customer_id": contract.customer_id, "customer_code": contract.customer.customer_code,
        "customer_name": contract.customer_name_snapshot or contract.customer.full_name,
        "identity": contract.customer_identity_snapshot or contract.customer.identity_number or "",
        "phone": contract.customer_phone_snapshot or contract.customer.phone,
        "address": contract.customer_address_snapshot or contract.customer.address,
        "branch": {"id": contract.branch_id, "name": contract.branch.name},
        "seller": {"id": contract.seller_id, "name": contract.seller.get_full_name().strip() or contract.seller.username},
        "plan": {"id": contract.plan_id, "name": contract.plan_name_snapshot or contract.plan.name},
        "total_price": money(contract.total_price), "total_paid": money(contract.total_paid_calc),
        "balance": money(contract.balance_calc), "overdue_amount": money(contract.overdue_amount_calc),
        "upcoming_amount": money(contract.upcoming_amount_calc),
        "initial_pending": money(max(contract.initial_payment_agreed - contract.initial_paid_calc, ZERO)),
        "overdue_installments": contract.overdue_count_calc,
        "days_overdue": (today - contract.oldest_overdue_date).days if contract.oldest_overdue_date else 0,
        "oldest_overdue_date": contract.oldest_overdue_date, "next_due_date": contract.next_due_date,
        "last_payment": ({"date": contract.last_payment_date, "amount": contract.last_payment_amount,
                          "number": contract.last_payment_number} if contract.last_payment_date else None),
        "last_collection_action": ({"date": contract.last_action_date, "outcome": contract.last_action_outcome}
                                   if contract.last_action_date else None),
        "active_promise": ({"date": contract.pending_promise_date, "amount": contract.pending_promise_amount,
                            "effective_status": PromiseStatus.BROKEN if contract.pending_promise_date < today else PromiseStatus.PENDING}
                           if contract.pending_promise_date else None),
        "collection_status": status, "collection_status_label": CollectionStatus(status).label,
        "priority": priority, "priority_label": CollectionPriority(priority).label,
    }


def filtered_totals(queryset, *, today=None):
    today = today or timezone.localdate()
    values = queryset.aggregate(
        pending=Coalesce(Sum("balance_calc"), Value(ZERO), output_field=MONEY_FIELD),
        overdue=Coalesce(Sum("overdue_amount_calc"), Value(ZERO), output_field=MONEY_FIELD),
        overdue_installments=Coalesce(Sum("overdue_count_calc"), Value(0), output_field=IntegerField()),
    )
    return {
        "contracts": queryset.count(), "customers": queryset.values("customer_id").distinct().count(),
        "pending": money(values["pending"]), "overdue": money(values["overdue"]),
        "upcoming": money(values["pending"] - values["overdue"]),
        "overdue_installments": values["overdue_installments"],
    }


def portfolio_summary(user, params=None, *, today=None):
    today = today or timezone.localdate()
    queryset = apply_portfolio_filters(portfolio_queryset(user, today=today), params or {}, today=today)
    totals = filtered_totals(queryset, today=today)
    current_customers = queryset.filter(overdue_amount_calc=0).values("customer_id").distinct().count()
    overdue_customers = queryset.filter(overdue_amount_calc__gt=0).values("customer_id").distinct().count()
    critical_customers = queryset.filter(
        oldest_overdue_date__lt=today - timedelta(days=SEVERE_OVERDUE_DAYS)
    ).values("customer_id").distinct().count()
    month_start = today.replace(day=1)
    collected = scope_payments(Payment.objects.all(), user).filter(
        status=PaymentStatus.CONFIRMED, payment_date__date__gte=month_start,
        payment_date__date__lte=today,
    ).aggregate(value=Sum("amount"))["value"] or ZERO
    return {
        "pending_portfolio": totals["pending"], "overdue_portfolio": totals["overdue"],
        "upcoming_portfolio": totals["upcoming"], "overdue_customers": overdue_customers,
        "overdue_installments": totals["overdue_installments"], "current_customers": current_customers,
        "critical_customers": critical_customers, "collected_this_month": money(collected),
    }


def aging_summary(user, params=None, *, today=None):
    today = today or timezone.localdate()
    contract_ids = apply_portfolio_filters(portfolio_queryset(user, today=today), params or {}, today=today).values("pk")
    base = Installment.objects.filter(
        contract_id__in=Subquery(contract_ids), schedule__status=ScheduleStatus.ACTIVE,
        due_date__lt=today, current_amount__gt=F("paid_amount"),
    ).exclude(status=InstallmentStatus.CANCELLED)
    pending = ExpressionWrapper(F("current_amount") - F("paid_amount"), output_field=MONEY_FIELD)
    buckets = []
    total = ZERO
    for value, label, minimum, maximum in AGING_BUCKETS:
        queryset = base.filter(due_date__lte=_date_for_min_days(today, minimum))
        if maximum is not None:
            queryset = queryset.filter(due_date__gt=_date_for_max_days(today, maximum))
        amount = queryset.aggregate(value=Sum(pending))["value"] or ZERO
        total += amount
        buckets.append({"value": value, "label": label, "amount": money(amount), "installments": queryset.count()})
    return {"buckets": buckets, "total_overdue": money(total)}


def _audit(organization, actor, event, description, *, action=None, promise=None):
    return CollectionAudit.objects.create(
        organization=organization, actor=actor, event=event, description=description,
        action=action, promise=promise,
    )


def _validate_contract_context(contract, customer):
    if contract.customer_id != customer.pk:
        raise ValidationError({"contract": "El contrato seleccionado no pertenece a este cliente."})
    if contract.organization_id != customer.organization_id:
        raise ValidationError({"customer": "Cliente y contrato deben pertenecer a la misma organización."})


@transaction.atomic
def create_collection_action(contract, customer, user, data):
    contract = Contract.objects.select_for_update().select_related("organization", "branch", "customer").get(pk=contract.pk)
    _validate_contract_context(contract, customer)
    contact_date = data.get("contact_date") or timezone.now()
    if contact_date > timezone.now():
        raise ValidationError({"contact_date": "La fecha de gestión no puede estar en el futuro."})
    action = CollectionAction.objects.create(
        organization=contract.organization, branch=contract.branch, customer=customer, contract=contract,
        action_type=data["action_type"], outcome=data["outcome"], notes=data["notes"].strip(),
        contact_date=contact_date, next_follow_up_date=data.get("next_follow_up_date"), created_by=user,
    )
    _audit(contract.organization, user, AuditEvent.ACTION_CREATED, "Gestión de cobranza registrada.", action=action)
    if action.outcome == CollectionOutcome.PROMISE_TO_PAY:
        create_payment_promise(contract, customer, user, {
            "collection_action": action,
            "promised_amount": data.get("promised_amount"), "promised_date": data.get("promised_date"),
        })
    return action


@transaction.atomic
def create_payment_promise(contract, customer, user, data):
    contract = Contract.objects.select_for_update().select_related("organization", "branch", "customer").get(pk=contract.pk)
    _validate_contract_context(contract, customer)
    promised_date = data.get("promised_date")
    if not promised_date or promised_date < timezone.localdate():
        raise ValidationError({"promised_date": "La fecha de promesa no puede ser anterior a hoy."})
    amount = money(data.get("promised_amount"))
    scoped = portfolio_queryset(user, include_paid=True).filter(pk=contract.pk).first()
    if not scoped:
        raise ValidationError({"contract": "No fue posible calcular el saldo del contrato."})
    if amount <= 0 or amount > scoped.balance_calc:
        raise ValidationError({"promised_amount": "El monto debe ser positivo y no exceder el saldo actual."})
    try:
        promise = PaymentPromise.objects.create(
            organization=contract.organization, branch=contract.branch, customer=customer, contract=contract,
            collection_action=data.get("collection_action"), promised_amount=amount,
            promised_date=promised_date, created_by=user,
        )
    except IntegrityError as exc:
        raise ConflictError("Este contrato ya tiene una promesa pendiente.") from exc
    _audit(contract.organization, user, AuditEvent.PROMISE_CREATED, "Promesa de pago registrada.", promise=promise)
    return promise


@transaction.atomic
def void_collection_action(action, user, reason):
    action = CollectionAction.objects.select_for_update().select_related("organization").get(pk=action.pk)
    if action.status == CollectionActionStatus.VOIDED:
        raise ConflictError("Esta gestión ya fue anulada.")
    action.status = CollectionActionStatus.VOIDED
    action.voided_by = user
    action.voided_at = timezone.now()
    action.void_reason = reason.strip()
    action.save(update_fields=("status", "voided_by", "voided_at", "void_reason", "updated_at"))
    promise = getattr(action, "payment_promise", None)
    if promise and promise.status == PromiseStatus.PENDING:
        _cancel_promise(promise, user, "Gestión asociada anulada.")
    _audit(action.organization, user, AuditEvent.ACTION_VOIDED, f"Gestión anulada: {reason[:200]}", action=action)
    return action


def _cancel_promise(promise, user, reason):
    promise.status = PromiseStatus.CANCELLED
    promise.resolved_by = user
    promise.resolved_at = timezone.now()
    promise.resolution_reason = reason.strip()
    promise.save(update_fields=("status", "resolved_by", "resolved_at", "resolution_reason", "updated_at"))
    _audit(promise.organization, user, AuditEvent.PROMISE_CANCELLED, reason[:500], promise=promise)
    return promise


@transaction.atomic
def cancel_promise(promise, user, reason):
    promise = PaymentPromise.objects.select_for_update().select_related("organization").get(pk=promise.pk)
    if promise.status != PromiseStatus.PENDING:
        raise ConflictError("Solo una promesa pendiente puede cancelarse.")
    return _cancel_promise(promise, user, reason)


@transaction.atomic
def acknowledge_broken_promise(promise, user, reason):
    promise = PaymentPromise.objects.select_for_update().select_related("organization").get(pk=promise.pk)
    if promise.status != PromiseStatus.PENDING or promise.promised_date >= timezone.localdate():
        raise ConflictError("Solo una promesa vencida pendiente puede marcarse como incumplida.")
    promise.status = PromiseStatus.BROKEN
    promise.resolved_by = user
    promise.resolved_at = timezone.now()
    promise.resolution_reason = reason.strip()
    promise.save(update_fields=("status", "resolved_by", "resolved_at", "resolution_reason", "updated_at"))
    _audit(promise.organization, user, AuditEvent.PROMISE_BROKEN, reason[:500], promise=promise)
    return promise


@transaction.atomic
def fulfill_promise(promise, payment, user):
    promise = PaymentPromise.objects.select_for_update().select_related("organization").get(pk=promise.pk)
    if promise.status != PromiseStatus.PENDING:
        raise ConflictError("Solo una promesa pendiente puede cumplirse.")
    if payment.status != PaymentStatus.CONFIRMED or payment.contract_id != promise.contract_id:
        raise ValidationError({"payment": "Selecciona un pago confirmado del mismo contrato."})
    deadline = promise.promised_date + timedelta(days=PROMISE_PAYMENT_GRACE_DAYS)
    if payment.amount < promise.promised_amount or payment.payment_date.date() > deadline or payment.created_at < promise.created_at:
        raise ValidationError({"payment": "El pago no satisface el monto o la ventana de esta promesa."})
    promise.status = PromiseStatus.FULFILLED
    promise.fulfilled_payment = payment
    promise.resolved_by = user
    promise.resolved_at = timezone.now()
    promise.resolution_reason = "Cumplimiento verificado contra pago confirmado."
    promise.save(update_fields=(
        "status", "fulfilled_payment", "resolved_by", "resolved_at", "resolution_reason", "updated_at",
    ))
    _audit(promise.organization, user, AuditEvent.PROMISE_FULFILLED, promise.resolution_reason, promise=promise)
    return promise


def actions_queryset(user):
    return scope_actions(CollectionAction.objects.select_related(
        "organization", "branch", "customer", "contract", "created_by", "voided_by", "payment_promise",
    ), user)


def promises_queryset(user):
    return scope_promises(PaymentPromise.objects.select_related(
        "organization", "branch", "customer", "contract", "collection_action",
        "fulfilled_payment", "created_by", "resolved_by",
    ), user)
