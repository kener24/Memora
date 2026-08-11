import hashlib
import json
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import CustomUser, RoleCode
from contracts.choices import ContractStatus
from contracts.exceptions import ConflictError
from contracts.models import Contract
from installments.choices import InstallmentStatus, ScheduleStatus
from installments.models import Installment
from payments.choices import PaymentMethod, PaymentStatus
from payments.models import Payment
from payments.services import money

from .choices import (
    AssignmentStatus, CollectionActionType, CollectionOutcome, CollectionActionStatus,
    OperationsAuditEvent, PromiseStatus, RouteVisitStatus, SettlementStatus, WorkSessionStatus,
)
from .models import (
    CollectionAssignment, CollectionOperationsAudit, CollectionRoute, CollectionRouteStop,
    CollectorProfile, CollectorSequence, CollectorSettlement, CollectorSettlementPayment,
    CollectorWorkSession, PaymentPromise, RouteVisit, SettlementSequence, SettlementSubmissionKey,
)
from .services import create_collection_action, filtered_totals, portfolio_queryset


ZERO = Decimal("0.00")


def user_name(user):
    return user.get_full_name().strip() or user.username


def is_collector(user):
    return getattr(getattr(user, "role", None), "code", None) == RoleCode.COLLECTOR


def validate_collector(collector, *, organization=None, branch=None):
    if not collector or not collector.is_active or not is_collector(collector):
        raise ValidationError({"collector": "Selecciona un usuario activo con rol cobrador."})
    if organization and collector.organization_id != organization.pk:
        raise ValidationError({"collector": "El cobrador pertenece a otra organización."})
    if branch and collector.branch_id != branch.pk:
        raise ValidationError({"collector": "El cobrador pertenece a otra sucursal."})
    return collector


def audit(organization, actor, event, description, **targets):
    return CollectionOperationsAudit.objects.create(
        organization=organization, actor=actor, event=event, description=description, **targets,
    )


@transaction.atomic
def ensure_collector_profile(collector, actor=None):
    validate_collector(collector)
    profile = CollectorProfile.objects.select_for_update().filter(user=collector).first()
    if profile:
        return profile
    sequence, _ = CollectorSequence.objects.select_for_update().get_or_create(
        organization=collector.organization
    )
    number = sequence.next_value
    sequence.next_value += 1
    sequence.save(update_fields=("next_value",))
    profile = CollectorProfile.objects.create(
        user=collector, employee_code=f"COB-{collector.organization_id:03d}-{number:05d}",
    )
    audit(
        collector.organization, actor or collector, OperationsAuditEvent.PROFILE_CREATED,
        f"Perfil {profile.employee_code} creado para {user_name(collector)}.",
    )
    return profile


def collector_users(user):
    queryset = CustomUser.objects.filter(
        is_active=True, role__code=RoleCode.COLLECTOR,
    ).select_related("organization", "branch", "role", "collector_profile")
    if user.is_superuser or getattr(getattr(user, "role", None), "code", None) == RoleCode.SUPERADMIN:
        return queryset
    return queryset.filter(organization_id=user.organization_id)


def validate_assignment_context(contract, collector):
    validate_collector(collector, organization=contract.organization, branch=contract.branch)
    if contract.status != ContractStatus.ACTIVE:
        raise ValidationError({"contract": "Solo se asignan contratos activos."})


@transaction.atomic
def assign_contract(contract, collector, actor, reason="Asignación operativa"):
    contract = Contract.objects.select_for_update().select_related("organization", "branch").get(pk=contract.pk)
    collector = CustomUser.objects.select_for_update().select_related("role", "organization", "branch").get(pk=collector.pk)
    validate_assignment_context(contract, collector)
    ensure_collector_profile(collector, actor)
    if CollectionAssignment.objects.filter(contract=contract, status=AssignmentStatus.ACTIVE).exists():
        raise ConflictError("Este contrato ya está asignado a otro cobrador.")
    try:
        assignment = CollectionAssignment.objects.create(
            organization=contract.organization, branch=contract.branch, contract=contract,
            collector=collector, assigned_by=actor, reason=reason.strip()[:500],
        )
    except IntegrityError as exc:
        raise ConflictError("Este contrato ya está asignado a otro cobrador.") from exc
    audit(
        contract.organization, actor, OperationsAuditEvent.ASSIGNMENT_CREATED,
        f"{contract.contract_number} asignado a {user_name(collector)}.", assignment=assignment,
    )
    return assignment


@transaction.atomic
def bulk_assign_contracts(contracts, collector, actor, reason="Asignación masiva"):
    contract_ids = sorted({item.pk for item in contracts})
    locked = list(Contract.objects.select_for_update().select_related(
        "organization", "branch"
    ).filter(pk__in=contract_ids).order_by("pk"))
    if len(locked) != len(contract_ids):
        raise ValidationError({"contracts": "Uno o más contratos ya no están disponibles."})
    if not locked:
        raise ValidationError({"contracts": "Selecciona al menos un contrato."})
    for contract in locked:
        validate_assignment_context(contract, collector)
    ensure_collector_profile(collector, actor)
    if CollectionAssignment.objects.filter(
        contract_id__in=contract_ids, status=AssignmentStatus.ACTIVE,
    ).exists():
        raise ConflictError("Uno o más contratos ya están asignados. Actualiza la selección.")
    assignments = []
    for contract in locked:
        assignment = CollectionAssignment.objects.create(
            organization=contract.organization, branch=contract.branch, contract=contract,
            collector=collector, assigned_by=actor, reason=reason.strip()[:500],
        )
        audit(
            contract.organization, actor, OperationsAuditEvent.ASSIGNMENT_CREATED,
            f"{contract.contract_number} asignado a {user_name(collector)} en lote.", assignment=assignment,
        )
        assignments.append(assignment)
    return assignments


@transaction.atomic
def reassign_contract(assignment, new_collector, actor, reason):
    if len(reason.strip()) < 5:
        raise ValidationError({"reason": "Explica el motivo de la reasignación."})
    assignment = CollectionAssignment.objects.select_for_update().select_related(
        "organization", "branch", "contract", "collector"
    ).get(pk=assignment.pk)
    if assignment.status != AssignmentStatus.ACTIVE:
        raise ConflictError("Solo una asignación activa puede reasignarse.")
    validate_assignment_context(assignment.contract, new_collector)
    if assignment.collector_id == new_collector.pk:
        raise ValidationError({"collector": "Selecciona un cobrador diferente."})
    ensure_collector_profile(new_collector, actor)
    assignment.status = AssignmentStatus.REASSIGNED
    assignment.effective_until = timezone.localdate()
    assignment.reason = f"{assignment.reason}\nReasignada: {reason.strip()}".strip()[:500]
    assignment.save(update_fields=("status", "effective_until", "reason", "updated_at"))
    replacement = CollectionAssignment.objects.create(
        organization=assignment.organization, branch=assignment.branch, contract=assignment.contract,
        collector=new_collector, assigned_by=actor, reason=reason.strip()[:500],
        previous_assignment=assignment,
    )
    audit(
        assignment.organization, actor, OperationsAuditEvent.ASSIGNMENT_REASSIGNED,
        f"{assignment.contract.contract_number}: {user_name(assignment.collector)} → {user_name(new_collector)}. {reason.strip()}",
        assignment=replacement,
    )
    return replacement


def collector_portfolio(actor, collector, *, include_paid=False):
    validate_collector(collector)
    return portfolio_queryset(actor, include_paid=include_paid).filter(
        collection_assignments__collector=collector,
        collection_assignments__status=AssignmentStatus.ACTIVE,
    ).distinct()


def assigned_contract_ids(collector):
    return CollectionAssignment.objects.filter(
        collector=collector, status=AssignmentStatus.ACTIVE,
    ).values("contract_id")


def payment_breakdown(queryset):
    result = {method: ZERO for method in PaymentMethod.values}
    for item in queryset.order_by().values("payment_method").annotate(total=Sum("amount")):
        result[item["payment_method"]] = money(item["total"] or ZERO)
    total = money(sum(result.values(), ZERO))
    return {
        "total_collected": total,
        "expected_cash": result[PaymentMethod.CASH],
        "cash_total": result[PaymentMethod.CASH],
        "transfer_total": result[PaymentMethod.TRANSFER],
        "card_total": result[PaymentMethod.CARD],
        "check_total": result[PaymentMethod.CHECK],
        "other_total": result[PaymentMethod.OTHER],
        "payment_count": queryset.count(),
    }


def collector_metrics(actor, collector, *, today=None):
    today = today or timezone.localdate()
    portfolio = collector_portfolio(actor, collector)
    totals = filtered_totals(portfolio)
    ids = portfolio.values("pk")
    due_today = Installment.objects.filter(
        contract_id__in=ids, schedule__status=ScheduleStatus.ACTIVE, due_date=today,
        current_amount__gt=F("paid_amount"),
    ).exclude(status=InstallmentStatus.CANCELLED)
    today_payments = Payment.objects.filter(
        received_by=collector, status=PaymentStatus.CONFIRMED, payment_date__date=today,
    )
    month_payments = Payment.objects.filter(
        received_by=collector, status=PaymentStatus.CONFIRMED,
        payment_date__date__gte=today.replace(day=1), payment_date__date__lte=today,
    )
    from .models import CollectionAction
    actions_today = CollectionAction.objects.filter(
        created_by=collector, status=CollectionActionStatus.ACTIVE, contact_date__date=today,
    )
    pending_promises = PaymentPromise.objects.filter(
        contract_id__in=ids, status=PromiseStatus.PENDING,
    )
    visits_today = RouteVisit.objects.filter(collector=collector, visit_date=today).exclude(
        status=RouteVisitStatus.PENDING
    )
    last_settlement = CollectorSettlement.objects.filter(collector=collector).first()
    breakdown = payment_breakdown(today_payments)
    return {
        "assigned_contracts": totals["contracts"], "assigned_customers": totals["customers"],
        "pending_portfolio": totals["pending"], "overdue_portfolio": totals["overdue"],
        "overdue_installments": totals["overdue_installments"],
        "due_today": money(sum((item.current_amount - item.paid_amount for item in due_today), ZERO)),
        "collected_today": breakdown["total_collected"], "collected_month": money(
            month_payments.aggregate(value=Sum("amount"))["value"] or ZERO
        ),
        "cash_today": breakdown["cash_total"], "transfer_today": breakdown["transfer_total"],
        "payments_today": breakdown["payment_count"], "actions_today": actions_today.count(),
        "customers_attended_today": len(
            set(actions_today.values_list("customer_id", flat=True))
            | set(visits_today.values_list("route_stop__customer_id", flat=True))
        ),
        "pending_promises": pending_promises.count(),
        "last_settlement": last_settlement.settlement_number if last_settlement else None,
    }


def bulk_collector_metrics(actor, collectors, *, today=None):
    """Build list metrics with a fixed number of queries, independent of collector count."""
    today = today or timezone.localdate()
    collectors = list(collectors)
    collector_ids = [item.pk for item in collectors]
    defaults = {
        "assigned_contracts": 0, "assigned_customers": 0, "pending_portfolio": ZERO,
        "overdue_portfolio": ZERO, "overdue_installments": 0, "due_today": ZERO,
        "collected_today": ZERO, "collected_month": ZERO, "cash_today": ZERO,
        "transfer_today": ZERO, "payments_today": 0, "actions_today": 0,
        "customers_attended_today": 0, "pending_promises": 0, "last_settlement": None,
    }
    result = {collector_id: dict(defaults) for collector_id in collector_ids}
    if not collector_ids:
        return result

    assignments = list(CollectionAssignment.objects.filter(
        collector_id__in=collector_ids, status=AssignmentStatus.ACTIVE,
    ).values("collector_id", "contract_id", "contract__customer_id"))
    contract_owner = {item["contract_id"]: item["collector_id"] for item in assignments}
    contract_ids = list(contract_owner)
    customer_sets = {collector_id: set() for collector_id in collector_ids}
    for item in assignments:
        metrics = result[item["collector_id"]]
        metrics["assigned_contracts"] += 1
        customer_sets[item["collector_id"]].add(item["contract__customer_id"])
    for collector_id, customers in customer_sets.items():
        result[collector_id]["assigned_customers"] = len(customers)

    for contract in portfolio_queryset(actor).filter(pk__in=contract_ids):
        collector_id = contract_owner[contract.pk]
        metrics = result[collector_id]
        metrics["pending_portfolio"] += money(contract.balance_calc)
        metrics["overdue_portfolio"] += money(contract.overdue_amount_calc)
        metrics["overdue_installments"] += contract.overdue_count_calc

    due_items = Installment.objects.filter(
        contract_id__in=contract_ids, schedule__status=ScheduleStatus.ACTIVE, due_date=today,
        current_amount__gt=F("paid_amount"),
    ).exclude(status=InstallmentStatus.CANCELLED).values("contract_id", "current_amount", "paid_amount")
    for item in due_items:
        collector_id = contract_owner.get(item["contract_id"])
        if collector_id:
            result[collector_id]["due_today"] += money(item["current_amount"] - item["paid_amount"])

    payment_rows = Payment.objects.filter(
        received_by_id__in=collector_ids, status=PaymentStatus.CONFIRMED,
        payment_date__date__gte=today.replace(day=1), payment_date__date__lte=today,
    ).order_by().values("received_by_id").annotate(
        month_total=Sum("amount"),
        today_total=Sum("amount", filter=Q(payment_date__date=today)),
        today_cash=Sum("amount", filter=Q(payment_date__date=today, payment_method=PaymentMethod.CASH)),
        today_transfer=Sum("amount", filter=Q(payment_date__date=today, payment_method=PaymentMethod.TRANSFER)),
        today_count=Count("id", filter=Q(payment_date__date=today)),
    )
    for item in payment_rows:
        metrics = result[item["received_by_id"]]
        metrics["collected_month"] = money(item["month_total"] or ZERO)
        metrics["collected_today"] = money(item["today_total"] or ZERO)
        metrics["cash_today"] = money(item["today_cash"] or ZERO)
        metrics["transfer_today"] = money(item["today_transfer"] or ZERO)
        metrics["payments_today"] = item["today_count"]

    from .models import CollectionAction
    action_rows = CollectionAction.objects.filter(
        created_by_id__in=collector_ids, status=CollectionActionStatus.ACTIVE,
        contact_date__date=today,
    ).values("created_by_id", "customer_id")
    attended = {collector_id: set() for collector_id in collector_ids}
    for item in action_rows:
        result[item["created_by_id"]]["actions_today"] += 1
        attended[item["created_by_id"]].add(item["customer_id"])
    for item in RouteVisit.objects.filter(
        collector_id__in=collector_ids, visit_date=today,
    ).exclude(status=RouteVisitStatus.PENDING).values("collector_id", "route_stop__customer_id"):
        attended[item["collector_id"]].add(item["route_stop__customer_id"])
    for collector_id, customers in attended.items():
        result[collector_id]["customers_attended_today"] = len(customers)

    promise_rows = PaymentPromise.objects.filter(
        contract_id__in=contract_ids, status=PromiseStatus.PENDING,
    ).order_by().values("contract_id").annotate(value=Count("id"))
    for item in promise_rows:
        collector_id = contract_owner.get(item["contract_id"])
        if collector_id:
            result[collector_id]["pending_promises"] += item["value"]

    seen = set()
    for item in CollectorSettlement.objects.filter(collector_id__in=collector_ids).values(
        "collector_id", "settlement_number"
    ).order_by("collector_id", "-submitted_at", "-id"):
        if item["collector_id"] not in seen:
            result[item["collector_id"]]["last_settlement"] = item["settlement_number"]
            seen.add(item["collector_id"])
    return result


def collector_today_portfolio(actor, collector, *, today=None):
    today = today or timezone.localdate()
    portfolio = collector_portfolio(actor, collector)
    due_ids = portfolio.filter(Q(next_due_date=today) | Q(overdue_amount_calc__gt=0)).values("pk")
    from .models import CollectionAction
    follow_ids = CollectionAction.objects.filter(
        created_by=collector, next_follow_up_date=today, status=CollectionActionStatus.ACTIVE,
    ).values("contract_id")
    promise_ids = PaymentPromise.objects.filter(
        contract_id__in=portfolio.values("pk"), promised_date=today, status=PromiseStatus.PENDING,
    ).values("contract_id")
    ids = set(due_ids.values_list("pk", flat=True))
    ids.update(follow_ids.values_list("contract_id", flat=True))
    ids.update(promise_ids.values_list("contract_id", flat=True))
    return portfolio.filter(pk__in=ids).order_by("oldest_overdue_date", "next_due_date", "customer_name_snapshot")


def session_payments(session, *, confirmed_only=False, unsettled_only=False):
    queryset = Payment.objects.filter(collector_session=session).select_related(
        "receipt", "customer", "contract", "received_by"
    )
    if confirmed_only:
        queryset = queryset.filter(status=PaymentStatus.CONFIRMED)
    if unsettled_only:
        queryset = queryset.filter(collector_settlement_item__isnull=True)
    return queryset


def work_session_summary(session):
    confirmed = session_payments(session, confirmed_only=True)
    result = payment_breakdown(confirmed)
    result.update({
        "voided_count": session_payments(session).filter(status=PaymentStatus.VOIDED).count(),
        "work_session": session.pk, "work_date": session.work_date, "status": session.status,
    })
    return result


@transaction.atomic
def start_work_session(collector, actor, notes=""):
    collector = CustomUser.objects.select_for_update().select_related("role", "organization", "branch").get(pk=collector.pk)
    validate_collector(collector)
    ensure_collector_profile(collector, actor)
    if not collector.branch_id:
        raise ValidationError({"branch": "El cobrador necesita una sucursal asignada."})
    if CollectorWorkSession.objects.filter(collector=collector, status=WorkSessionStatus.OPEN).exists():
        raise ConflictError("Este cobrador ya tiene una jornada abierta.")
    if CollectorWorkSession.objects.filter(
        collector=collector, branch=collector.branch, work_date=timezone.localdate(),
    ).exists():
        raise ConflictError("Este cobrador ya registró una jornada para hoy.")
    try:
        session = CollectorWorkSession.objects.create(
            organization=collector.organization, branch=collector.branch, collector=collector,
            opened_by=actor, notes=notes.strip()[:1000],
        )
    except IntegrityError as exc:
        raise ConflictError("Este cobrador ya tiene una jornada abierta.") from exc
    audit(
        collector.organization, actor, OperationsAuditEvent.SESSION_STARTED,
        f"Jornada iniciada por {user_name(collector)}.", work_session=session,
    )
    return session


@transaction.atomic
def close_work_session(session, actor, notes=""):
    session = CollectorWorkSession.objects.select_for_update().select_related("organization").get(pk=session.pk)
    if session.status != WorkSessionStatus.OPEN:
        raise ConflictError("La jornada ya fue cerrada.")
    session.status = WorkSessionStatus.CLOSED
    session.ended_at = timezone.now()
    session.closed_by = actor
    if notes.strip():
        session.notes = f"{session.notes}\nCierre: {notes.strip()}".strip()[:1000]
    session.save(update_fields=("status", "ended_at", "closed_by", "notes", "updated_at"))
    audit(
        session.organization, actor, OperationsAuditEvent.SESSION_CLOSED,
        f"Jornada cerrada con {work_session_summary(session)['payment_count']} pagos confirmados.",
        work_session=session,
    )
    return session


def settlement_payment_queryset(session):
    return session_payments(session, confirmed_only=True, unsettled_only=True).order_by(
        "payment_date", "created_at", "id"
    )


def payment_fingerprint(payments):
    data = list(payments.values_list("id", "status", "amount", "payment_method"))
    return hashlib.sha256(json.dumps(data, default=str, separators=(",", ":")).encode()).hexdigest()


def settlement_preview(session):
    payments = settlement_payment_queryset(session)
    result = payment_breakdown(payments)
    result.update({
        "payment_fingerprint": payment_fingerprint(payments),
        "payments": [{
            "id": item.pk, "payment_number": item.payment_number,
            "receipt_number": item.receipt.receipt_number, "customer": item.customer.full_name,
            "contract": item.contract.contract_number, "method": item.payment_method,
            "method_label": item.get_payment_method_display(), "amount": money(item.amount),
            "payment_date": item.payment_date,
        } for item in payments],
    })
    return result


def allocate_settlement_number(organization):
    sequence, _ = SettlementSequence.objects.select_for_update().get_or_create(organization=organization)
    number = sequence.next_value
    sequence.next_value += 1
    sequence.save(update_fields=("next_value",))
    return f"LIQ-{number:06d}"


def settlement_payload_digest(session, reported_cash, notes, fingerprint):
    payload = {
        "session": session.pk, "reported_cash": str(money(reported_cash)),
        "notes": notes.strip(), "fingerprint": fingerprint,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@transaction.atomic
def submit_settlement(session, actor, reported_cash, notes, fingerprint, idempotency_key):
    session = CollectorWorkSession.objects.select_for_update().select_related(
        "organization", "branch", "collector"
    ).get(pk=session.pk)
    if session.status != WorkSessionStatus.CLOSED:
        raise ConflictError("Cierra la jornada antes de presentar la liquidación.")
    reported_cash = money(reported_cash)
    if reported_cash < 0:
        raise ValidationError({"reported_cash": "El efectivo reportado no puede ser negativo."})
    digest = settlement_payload_digest(session, reported_cash, notes, fingerprint)
    existing_key = SettlementSubmissionKey.objects.select_for_update().filter(
        organization=session.organization, key=idempotency_key,
    ).first()
    if existing_key:
        if existing_key.payload_hash == digest and existing_key.settlement_id:
            return existing_key.settlement, False
        raise ConflictError("Esta clave de idempotencia ya fue utilizada con otra liquidación.")
    if CollectorSettlement.objects.filter(work_session=session).exists():
        raise ConflictError("Esta jornada ya tiene una liquidación.")
    preview = settlement_preview(session)
    if preview["payment_fingerprint"] != fingerprint:
        raise ConflictError("La liquidación cambió porque se registraron nuevos pagos. Actualiza antes de continuar.")
    difference = money(reported_cash - preview["expected_cash"])
    if difference and len(notes.strip()) < 5:
        raise ValidationError({"notes": "Explica la diferencia de efectivo antes de presentar."})
    settlement = CollectorSettlement.objects.create(
        organization=session.organization, branch=session.branch, collector=session.collector,
        work_session=session, settlement_number=allocate_settlement_number(session.organization),
        total_collected=preview["total_collected"], expected_cash=preview["expected_cash"],
        reported_cash=reported_cash, transfer_total=preview["transfer_total"],
        card_total=preview["card_total"], check_total=preview["check_total"],
        other_total=preview["other_total"], difference=difference,
        payment_fingerprint=preview["payment_fingerprint"], submitted_by=actor, notes=notes.strip()[:1000],
    )
    payments = list(settlement_payment_queryset(session).select_for_update())
    CollectorSettlementPayment.objects.bulk_create([
        CollectorSettlementPayment(
            settlement=settlement, payment=payment,
            payment_number_snapshot=payment.payment_number,
            receipt_number_snapshot=payment.receipt.receipt_number,
            customer_name_snapshot=payment.receipt.customer_name_snapshot,
            contract_number_snapshot=payment.contract.contract_number,
            payment_method_snapshot=payment.payment_method, amount_snapshot=payment.amount,
        ) for payment in payments
    ])
    SettlementSubmissionKey.objects.create(
        organization=session.organization, key=idempotency_key, payload_hash=digest,
        settlement=settlement, created_by=actor,
    )
    audit(
        session.organization, actor, OperationsAuditEvent.SETTLEMENT_SUBMITTED,
        f"{settlement.settlement_number} presentada por L {settlement.total_collected:,.2f}.",
        settlement=settlement, work_session=session,
    )
    return settlement, True


@transaction.atomic
def review_settlement(settlement, actor, notes):
    settlement = CollectorSettlement.objects.select_for_update().select_related("organization").get(pk=settlement.pk)
    if settlement.status != SettlementStatus.SUBMITTED:
        raise ConflictError("Solo una liquidación presentada puede revisarse.")
    settlement.status = SettlementStatus.REVIEWED
    settlement.reviewed_by = actor
    settlement.reviewed_at = timezone.now()
    settlement.review_notes = notes.strip()[:1000]
    settlement.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_notes", "updated_at"))
    audit(
        settlement.organization, actor, OperationsAuditEvent.SETTLEMENT_REVIEWED,
        f"{settlement.settlement_number} revisada.", settlement=settlement,
    )
    return settlement


@transaction.atomic
def decide_settlement(settlement, actor, *, accept, reason):
    settlement = CollectorSettlement.objects.select_for_update().select_related("organization", "collector").get(pk=settlement.pk)
    if settlement.status not in {SettlementStatus.SUBMITTED, SettlementStatus.REVIEWED}:
        raise ConflictError("Esta liquidación ya tiene una decisión final.")
    if actor.pk == settlement.collector_id:
        raise ValidationError({"reviewer": "El cobrador no puede decidir su propia liquidación."})
    if not accept and len(reason.strip()) < 5:
        raise ValidationError({"reason": "Explica el motivo del rechazo."})
    if accept and settlement.difference and len(reason.strip()) < 5 and len(settlement.review_notes.strip()) < 5:
        raise ValidationError({"reason": "Documenta la aceptación de la diferencia."})
    settlement.status = SettlementStatus.ACCEPTED if accept else SettlementStatus.REJECTED
    settlement.reviewed_by = actor
    settlement.reviewed_at = timezone.now()
    settlement.review_notes = reason.strip()[:1000] or settlement.review_notes
    settlement.save(update_fields=("status", "reviewed_by", "reviewed_at", "review_notes", "updated_at"))
    event = OperationsAuditEvent.SETTLEMENT_ACCEPTED if accept else OperationsAuditEvent.SETTLEMENT_REJECTED
    audit(
        settlement.organization, actor, event,
        f"{settlement.settlement_number} {'aceptada' if accept else 'rechazada'}. {reason.strip()}",
        settlement=settlement,
    )
    return settlement


@transaction.atomic
def record_route_visit(route_stop, collector, status, notes=""):
    route_stop = CollectionRouteStop.objects.select_for_update().select_related(
        "route__organization", "route__branch", "customer"
    ).get(pk=route_stop.pk)
    if route_stop.route.collector_id and route_stop.route.collector_id != collector.pk:
        raise ValidationError({"route": "Esta ruta pertenece a otro cobrador."})
    if status not in RouteVisitStatus.values:
        raise ValidationError({"status": "Selecciona un estado de visita válido."})
    visit, _ = RouteVisit.objects.update_or_create(
        route_stop=route_stop, collector=collector, visit_date=timezone.localdate(),
        defaults={"route": route_stop.route, "status": status, "notes": notes.strip()[:1000]},
    )
    if status == RouteVisitStatus.NOT_FOUND and not visit.collection_action_id:
        assignment = CollectionAssignment.objects.filter(
            collector=collector, status=AssignmentStatus.ACTIVE,
            contract__customer=route_stop.customer,
        ).select_related("contract__customer").first()
        if assignment:
            action = create_collection_action(assignment.contract, assignment.contract.customer, collector, {
                "action_type": CollectionActionType.VISIT, "outcome": CollectionOutcome.NOT_FOUND,
                "notes": notes.strip() or f"Cliente no encontrado durante {route_stop.route.name}.",
            })
            visit.collection_action = action
            visit.save(update_fields=("collection_action", "updated_at"))
    return visit
