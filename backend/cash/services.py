import hashlib
import json
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import RoleCode
from collection_management.choices import SettlementStatus
from collection_management.models import CollectorSettlement
from contracts.access import is_branch_restricted
from contracts.exceptions import ConflictError
from payments.access import scope_payments
from payments.choices import PaymentMethod, PaymentStatus
from payments.models import Payment
from payments.services import money

from .access import role_code, scope_cash
from .choices import (
    CashAuditEvent, CashIdempotencyOperation, CashMovementCategory, CashMovementDirection,
    CashMovementStatus, CashMovementType, CashReceptionStatus, CashSessionStatus,
)
from .models import (
    CashAudit, CashCount, CashCountDenomination, CashIdempotencyKey, CashMovement,
    CashRegister, CashSequence, CashSession, CollectorSettlementReception,
)


ZERO = Decimal("0.00")
CASH_DENOMINATIONS = (
    Decimal("0.05"), Decimal("0.10"), Decimal("0.20"), Decimal("0.50"),
    Decimal("1.00"), Decimal("2.00"), Decimal("5.00"), Decimal("10.00"),
    Decimal("20.00"), Decimal("50.00"), Decimal("100.00"), Decimal("200.00"),
    Decimal("500.00"),
)
INCOME_CATEGORIES = {
    CashMovementCategory.EXTRAORDINARY_INCOME,
    CashMovementCategory.TEMPORARY_CONTRIBUTION,
    CashMovementCategory.OTHER_INCOME,
}
EXPENSE_CATEGORIES = {
    CashMovementCategory.OPERATING_EXPENSE,
    CashMovementCategory.MINOR_PURCHASE,
    CashMovementCategory.AUTHORIZED_REFUND,
    CashMovementCategory.OTHER_EXPENSE,
}


def is_cash_method(payment_method):
    return payment_method == PaymentMethod.CASH


def user_name(user):
    return user.get_full_name().strip() or user.username


def audit(organization, actor, event, description, **relations):
    return CashAudit.objects.create(
        organization=organization, actor=actor, event=event,
        description=description.strip()[:1000], **relations,
    )


def _sequence_value(organization, field):
    sequence, _ = CashSequence.objects.select_for_update().get_or_create(organization=organization)
    value = getattr(sequence, field)
    setattr(sequence, field, value + 1)
    sequence.save(update_fields=(field,))
    return value


def allocate_register_code(organization):
    return f"CAJ-{_sequence_value(organization, 'next_register'):03d}"


def allocate_session_number(organization):
    return f"CS-{_sequence_value(organization, 'next_session'):06d}"


def allocate_movement_number(organization):
    return f"MOV-{_sequence_value(organization, 'next_movement'):06d}"


def allocate_reception_number(organization):
    return f"RLI-{_sequence_value(organization, 'next_reception'):06d}"


def payload_hash(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _idempotent_resource(organization, key, operation, digest, model, actor):
    existing = CashIdempotencyKey.objects.select_for_update().filter(
        organization=organization, key=key
    ).first()
    if not existing:
        return None
    if (
        existing.operation != operation or existing.payload_hash != digest
        or existing.created_by_id != actor.pk
    ):
        raise ConflictError("Esta clave de idempotencia ya fue utilizada con otros datos.")
    try:
        return model.objects.get(pk=existing.resource_id)
    except model.DoesNotExist as exc:
        raise ConflictError("El resultado idempotente ya no está disponible.") from exc


def _save_idempotency(organization, key, operation, digest, resource, actor):
    CashIdempotencyKey.objects.create(
        organization=organization, key=key, operation=operation, payload_hash=digest,
        resource_type=resource._meta.label_lower, resource_id=resource.pk, created_by=actor,
    )


@transaction.atomic
def create_cash_register(organization, branch, actor, name, description=""):
    if branch.organization_id != organization.pk:
        raise ValidationError({"branch": "La sucursal pertenece a otra organización."})
    item = CashRegister(
        organization=organization, branch=branch, code=allocate_register_code(organization),
        name=name.strip(), description=description.strip(), created_by=actor,
    )
    item.full_clean()
    item.save()
    audit(
        organization, actor, CashAuditEvent.REGISTER_CREATED,
        f"Se creó {item.code} · {item.name} en {branch.name}.", cash_register=item,
    )
    return item


@transaction.atomic
def update_cash_register(register, actor, **changes):
    register = CashRegister.objects.select_for_update().select_related("organization", "branch").get(pk=register.pk)
    if CashSession.objects.filter(cash_register=register, status=CashSessionStatus.OPEN).exists() and changes.get("is_active") is False:
        raise ConflictError("No puedes inactivar una caja con una sesión abierta.")
    old_active = register.is_active
    for field in ("name", "description", "is_active"):
        if field in changes:
            value = changes[field]
            setattr(register, field, value.strip() if isinstance(value, str) else value)
    register.full_clean()
    register.save(update_fields=("name", "description", "is_active", "updated_at"))
    if old_active != register.is_active:
        event = CashAuditEvent.REGISTER_ACTIVATED if register.is_active else CashAuditEvent.REGISTER_DEACTIVATED
    else:
        event = CashAuditEvent.REGISTER_UPDATED
    if old_active != register.is_active:
        action_label = "activada" if register.is_active else "inactivada"
    else:
        action_label = "actualizada"
    audit(
        register.organization, actor, event,
        f"{register.code} fue {action_label}.",
        cash_register=register,
    )
    return register


def _assert_session_actor(session, actor):
    if role_code(actor) == RoleCode.CASHIER and session.cashier_id != actor.pk:
        raise ValidationError({"cash_session": "Solo puedes operar tu propia sesión de caja."})


def _locked_session(session, actor=None):
    locked = CashSession.objects.select_for_update().select_related(
        "organization", "branch", "cash_register", "cashier"
    ).get(pk=session.pk)
    if actor:
        _assert_session_actor(locked, actor)
    return locked


def _locked_open_session(session, actor=None):
    locked = _locked_session(session, actor)
    if locked.status != CashSessionStatus.OPEN:
        raise ConflictError("El movimiento no puede registrarse porque la caja está cerrada.")
    return locked


@transaction.atomic
def open_cash_session(cash_register, actor, opening_cash, notes, idempotency_key):
    cash_register = CashRegister.objects.select_for_update().select_related(
        "organization", "branch"
    ).get(pk=cash_register.pk)
    opening_cash = money(opening_cash)
    if opening_cash < 0:
        raise ValidationError({"opening_cash": "El fondo inicial no puede ser negativo."})
    digest = payload_hash({
        "cash_register": cash_register.pk, "cashier": actor.pk,
        "opening_cash": str(opening_cash), "notes": notes.strip(),
    })
    existing = _idempotent_resource(
        cash_register.organization, idempotency_key, CashIdempotencyOperation.OPEN_SESSION,
        digest, CashSession, actor,
    )
    if existing:
        return existing, False
    if not cash_register.is_active:
        raise ValidationError({"cash_register": "La caja seleccionada está inactiva."})
    if actor.organization_id != cash_register.organization_id:
        raise ValidationError({"cash_register": "La caja pertenece a otra organización."})
    if actor.branch_id and actor.branch_id != cash_register.branch_id:
        raise ValidationError({"cash_register": "La caja pertenece a otra sucursal."})
    if CashSession.objects.filter(cash_register=cash_register, status=CashSessionStatus.OPEN).exists():
        raise ConflictError("Esta caja ya tiene una sesión abierta.")
    if CashSession.objects.filter(
        branch=cash_register.branch, cashier=actor, status=CashSessionStatus.OPEN
    ).exists():
        raise ConflictError("Ya tienes una sesión de caja abierta en esta sucursal.")
    try:
        session = CashSession.objects.create(
            organization=cash_register.organization, branch=cash_register.branch,
            cash_register=cash_register, cashier=actor,
            session_number=allocate_session_number(cash_register.organization),
            opening_cash=opening_cash, opened_by=actor, notes=notes.strip()[:2000],
        )
    except IntegrityError as exc:
        raise ConflictError("Esta caja ya tiene una sesión abierta.") from exc
    _save_idempotency(
        cash_register.organization, idempotency_key, CashIdempotencyOperation.OPEN_SESSION,
        digest, session, actor,
    )
    audit(
        cash_register.organization, actor, CashAuditEvent.SESSION_OPENED,
        f"{session.session_number} abierta en {cash_register.name} con fondo L {opening_cash:,.2f}.",
        cash_register=cash_register, cash_session=session,
    )
    return session, True


def current_cash_session(user):
    return CashSession.objects.select_related(
        "organization", "branch", "cash_register", "cashier", "opened_by", "closed_by"
    ).filter(cashier=user, status=CashSessionStatus.OPEN).first()


def session_movements(session, confirmed_only=False):
    queryset = CashMovement.objects.filter(cash_session=session)
    if confirmed_only:
        queryset = queryset.filter(status=CashMovementStatus.CONFIRMED)
    return queryset


def _sum(queryset, field="amount"):
    return money(queryset.aggregate(value=Coalesce(Sum(field), ZERO))["value"])


def session_summary(session):
    confirmed = session_movements(session, confirmed_only=True)
    cash_rows = confirmed.filter(affects_cash=True)
    cash_in = _sum(cash_rows.filter(direction=CashMovementDirection.IN))
    cash_out = _sum(cash_rows.filter(direction=CashMovementDirection.OUT))
    financial_in = _sum(confirmed.filter(direction=CashMovementDirection.IN))
    financial_out = _sum(confirmed.filter(direction=CashMovementDirection.OUT))
    method_totals = {}
    for method in PaymentMethod.values:
        incoming = _sum(confirmed.filter(direction=CashMovementDirection.IN, payment_method=method))
        outgoing = _sum(confirmed.filter(direction=CashMovementDirection.OUT, payment_method=method))
        method_totals[method] = money(incoming - outgoing)
    receptions = session.settlement_receptions.filter(status=CashReceptionStatus.CONFIRMED)
    reception_fields = {
        PaymentMethod.TRANSFER: "transfer_total", PaymentMethod.CARD: "card_total",
        PaymentMethod.CHECK: "check_total", PaymentMethod.OTHER: "other_total",
    }
    for method, field in reception_fields.items():
        method_totals[method] = money(method_totals[method] + _sum(receptions, field))
    expected_cash = money(session.opening_cash + cash_in - cash_out)
    latest_count = session.cash_counts.order_by("-counted_at", "-id").first()
    return {
        "opening_cash": money(session.opening_cash), "cash_in": cash_in, "cash_out": cash_out,
        "expected_cash": expected_cash, "financial_in": financial_in,
        "financial_out": financial_out, "financial_net": money(financial_in - financial_out),
        "method_totals": method_totals,
        "movement_count": session_movements(session).count(),
        "voided_count": session_movements(session).filter(status=CashMovementStatus.VOIDED).count(),
        "latest_count": latest_count,
    }


def movement_fingerprint(session):
    rows = list(session_movements(session).order_by("id").values_list(
        "id", "status", "amount", "direction", "payment_method", "affects_cash", "updated_at"
    ))
    return payload_hash({"session": session.pk, "opening_cash": str(session.opening_cash), "movements": rows})


def _validate_manual_movement(direction, category, description):
    allowed = INCOME_CATEGORIES if direction == CashMovementDirection.IN else EXPENSE_CATEGORIES
    if category not in allowed:
        raise ValidationError({"category": "Selecciona una categoría válida para la dirección del movimiento."})
    if len(description.strip()) < 5:
        raise ValidationError({"description": "Describe el motivo del movimiento con al menos 5 caracteres."})


def _create_movement(
    session, actor, *, movement_type, direction, category, amount, payment_method,
    description, reference="", payment=None, settlement_reception=None,
):
    amount = money(amount)
    if amount <= 0:
        raise ValidationError({"amount": "El monto debe ser mayor que cero."})
    movement = CashMovement(
        organization=session.organization, branch=session.branch, cash_session=session,
        movement_number=allocate_movement_number(session.organization), movement_type=movement_type,
        direction=direction, category=category, amount=amount, payment_method=payment_method,
        affects_cash=is_cash_method(payment_method), description=description.strip()[:2000],
        reference=reference.strip()[:160], payment=payment,
        settlement_reception=settlement_reception, created_by=actor,
    )
    movement.full_clean()
    movement.save()
    audit(
        session.organization, actor, CashAuditEvent.MOVEMENT_CREATED,
        f"{movement.movement_number}: {movement.get_direction_display()} L {amount:,.2f} por {movement.get_movement_type_display()}.",
        cash_register=session.cash_register, cash_session=session, cash_movement=movement,
        settlement_reception=settlement_reception,
    )
    return movement


@transaction.atomic
def create_manual_movement(
    session, actor, *, direction, category, amount, payment_method,
    description, reference, idempotency_key,
):
    session = _locked_session(session, actor)
    amount = money(amount)
    _validate_manual_movement(direction, category, description)
    operation = (
        CashIdempotencyOperation.CREATE_INCOME
        if direction == CashMovementDirection.IN else CashIdempotencyOperation.CREATE_EXPENSE
    )
    digest = payload_hash({
        "session": session.pk, "direction": direction, "category": category,
        "amount": str(amount), "payment_method": payment_method,
        "description": description.strip(), "reference": reference.strip(),
    })
    existing = _idempotent_resource(
        session.organization, idempotency_key, operation, digest, CashMovement, actor
    )
    if existing:
        return existing, False
    if session.status != CashSessionStatus.OPEN:
        raise ConflictError("El movimiento no puede registrarse porque la caja está cerrada.")
    if direction == CashMovementDirection.OUT and is_cash_method(payment_method):
        if amount > session_summary(session)["expected_cash"]:
            raise ValidationError({"amount": "El egreso supera el efectivo disponible."})
    movement = _create_movement(
        session, actor,
        movement_type=(
            CashMovementType.MANUAL_INCOME
            if direction == CashMovementDirection.IN else CashMovementType.EXPENSE
        ),
        direction=direction, category=category, amount=amount,
        payment_method=payment_method, description=description, reference=reference,
    )
    _save_idempotency(session.organization, idempotency_key, operation, digest, movement, actor)
    return movement, True


def resolve_cash_session_for_payment(user, branch):
    code = role_code(user)
    if code == RoleCode.COLLECTOR:
        return None
    session = CashSession.objects.select_for_update().filter(
        cashier=user, branch=branch, status=CashSessionStatus.OPEN
    ).select_related("organization", "branch", "cash_register", "cashier").first()
    if code == RoleCode.CASHIER and not session:
        raise ValidationError({"cash_session": "No existe una sesión abierta. Abre tu caja antes de registrar pagos."})
    return session


def create_payment_movement(payment, session, actor):
    if not session:
        return None
    existing = CashMovement.objects.filter(payment=payment).first()
    if existing:
        return existing
    return _create_movement(
        session, actor, movement_type=CashMovementType.CUSTOMER_PAYMENT,
        direction=CashMovementDirection.IN, category=CashMovementCategory.CUSTOMER_PAYMENT,
        amount=payment.amount, payment_method=payment.payment_method,
        description=f"Pago de cliente {payment.payment_number} · {payment.contract.contract_number}.",
        reference=payment.reference, payment=payment,
    )


def void_payment_movement(payment, actor, reason):
    movement = CashMovement.objects.select_for_update().select_related(
        "cash_session__cash_register", "organization"
    ).filter(payment=payment).first()
    if not movement:
        return None
    if movement.status == CashMovementStatus.VOIDED:
        return movement
    if movement.cash_session.status != CashSessionStatus.OPEN:
        raise ConflictError(
            "Este pago pertenece a una caja cerrada y no puede anularse con el flujo simple. "
            "Registra la incidencia para un ajuste administrativo posterior."
        )
    if (
        movement.affects_cash
        and movement.direction == CashMovementDirection.IN
        and session_summary(movement.cash_session)["expected_cash"] < movement.amount
    ):
        raise ConflictError(
            "La anulación dejaría el efectivo esperado en negativo. "
            "Revierte primero los egresos relacionados o registra la incidencia para un ajuste posterior."
        )
    movement.status = CashMovementStatus.VOIDED
    movement.voided_at = timezone.now()
    movement.voided_by = actor
    movement.void_reason = reason.strip()[:2000]
    movement.save(update_fields=("status", "voided_at", "voided_by", "void_reason", "updated_at"))
    audit(
        movement.organization, actor, CashAuditEvent.MOVEMENT_VOIDED,
        f"{movement.movement_number} fue anulado con {payment.payment_number}. Motivo: {reason[:300]}",
        cash_register=movement.cash_session.cash_register, cash_session=movement.cash_session,
        cash_movement=movement,
    )
    return movement


@transaction.atomic
def void_manual_movement(movement, actor, reason):
    movement = CashMovement.objects.select_for_update().select_related(
        "cash_session__cash_register", "organization"
    ).get(pk=movement.pk)
    _assert_session_actor(movement.cash_session, actor)
    if movement.status == CashMovementStatus.VOIDED:
        raise ConflictError("Este movimiento ya fue anulado.")
    if movement.cash_session.status != CashSessionStatus.OPEN:
        raise ConflictError("No puedes anular movimientos de una caja cerrada.")
    if movement.payment_id or movement.settlement_reception_id:
        raise ConflictError("Este movimiento debe corregirse desde su operación de origen.")
    if (
        movement.affects_cash
        and movement.direction == CashMovementDirection.IN
        and session_summary(movement.cash_session)["expected_cash"] < movement.amount
    ):
        raise ConflictError(
            "La anulación dejaría el efectivo esperado en negativo. "
            "Revierte primero los egresos relacionados."
        )
    if len(reason.strip()) < 5:
        raise ValidationError({"reason": "Explica el motivo de anulación."})
    movement.status = CashMovementStatus.VOIDED
    movement.voided_at = timezone.now()
    movement.voided_by = actor
    movement.void_reason = reason.strip()[:2000]
    movement.save(update_fields=("status", "voided_at", "voided_by", "void_reason", "updated_at"))
    audit(
        movement.organization, actor, CashAuditEvent.MOVEMENT_VOIDED,
        f"{movement.movement_number} anulado. Motivo: {reason[:300]}",
        cash_register=movement.cash_session.cash_register, cash_session=movement.cash_session,
        cash_movement=movement,
    )
    return movement


@transaction.atomic
def receive_collector_settlement(
    session, settlement, actor, cash_received, notes, idempotency_key,
):
    session = _locked_session(session, actor)
    settlement = CollectorSettlement.objects.select_for_update().select_related(
        "organization", "branch", "collector", "work_session"
    ).get(pk=settlement.pk)
    cash_received = money(cash_received)
    if cash_received < 0:
        raise ValidationError({"cash_received_by_cashier": "El efectivo recibido no puede ser negativo."})
    digest = payload_hash({
        "session": session.pk, "settlement": settlement.pk,
        "cash_received": str(cash_received), "notes": notes.strip(),
    })
    existing = _idempotent_resource(
        session.organization, idempotency_key, CashIdempotencyOperation.RECEIVE_SETTLEMENT,
        digest, CollectorSettlementReception, actor,
    )
    if existing:
        return existing, False
    if session.status != CashSessionStatus.OPEN:
        raise ConflictError("El movimiento no puede registrarse porque la caja está cerrada.")
    if settlement.organization_id != session.organization_id or settlement.branch_id != session.branch_id:
        raise ValidationError({"collector_settlement": "La liquidación pertenece a otra organización o sucursal."})
    if settlement.status != SettlementStatus.ACCEPTED:
        raise ValidationError({"collector_settlement": "Solo puede recibirse una liquidación aceptada."})
    if CollectorSettlementReception.objects.filter(collector_settlement=settlement).exists():
        raise ConflictError("Esta liquidación ya fue recibida.")
    collector_difference = money(settlement.reported_cash - settlement.expected_cash)
    delivery_difference = money(cash_received - settlement.reported_cash)
    total_difference = money(cash_received - settlement.expected_cash)
    if delivery_difference and len(notes.strip()) < 5:
        raise ValidationError({"notes": "Explica la diferencia entre lo reportado y el efectivo recibido."})
    try:
        reception = CollectorSettlementReception.objects.create(
            organization=session.organization, branch=session.branch, cash_session=session,
            collector_settlement=settlement,
            reception_number=allocate_reception_number(session.organization),
            expected_cash=settlement.expected_cash,
            reported_cash_by_collector=settlement.reported_cash,
            cash_received_by_cashier=cash_received,
            collector_difference=collector_difference,
            delivery_difference=delivery_difference,
            total_difference_vs_expected=total_difference,
            transfer_total=settlement.transfer_total, card_total=settlement.card_total,
            check_total=settlement.check_total, other_total=settlement.other_total,
            received_by=actor, notes=notes.strip()[:2000], status=CashReceptionStatus.CONFIRMED,
        )
    except IntegrityError as exc:
        raise ConflictError("Esta liquidación ya fue recibida.") from exc
    if cash_received > 0:
        _create_movement(
            session, actor, movement_type=CashMovementType.COLLECTOR_SETTLEMENT,
            direction=CashMovementDirection.IN,
            category=CashMovementCategory.COLLECTOR_SETTLEMENT,
            amount=cash_received, payment_method=PaymentMethod.CASH,
            description=f"Recepción {reception.reception_number} de {settlement.settlement_number}.",
            reference=settlement.settlement_number, settlement_reception=reception,
        )
    _save_idempotency(
        session.organization, idempotency_key, CashIdempotencyOperation.RECEIVE_SETTLEMENT,
        digest, reception, actor,
    )
    audit(
        session.organization, actor, CashAuditEvent.SETTLEMENT_RECEIVED,
        f"{reception.reception_number}: se recibieron L {cash_received:,.2f} de {settlement.settlement_number}.",
        cash_register=session.cash_register, cash_session=session, settlement_reception=reception,
    )
    if total_difference:
        audit(
            session.organization, actor, CashAuditEvent.DIFFERENCE_DETECTED,
            f"{reception.reception_number} presenta diferencia total vs esperado de L {total_difference:,.2f}.",
            cash_register=session.cash_register, cash_session=session, settlement_reception=reception,
        )
    return reception, True


def _normalized_denominations(rows):
    normalized = []
    seen = set()
    for row in rows:
        denomination = money(row["denomination"])
        quantity = row["quantity"]
        if denomination not in CASH_DENOMINATIONS:
            raise ValidationError({"denominations": f"La denominación L {denomination} no está permitida."})
        if denomination in seen:
            raise ValidationError({"denominations": "No repitas una denominación."})
        if quantity < 0:
            raise ValidationError({"denominations": "Las cantidades no pueden ser negativas."})
        seen.add(denomination)
        if quantity:
            normalized.append((denomination, quantity, money(denomination * quantity)))
    return normalized


@transaction.atomic
def perform_cash_count(
    session, actor, *, denominations, counted_cash, difference_reason, idempotency_key,
):
    session = _locked_session(session, actor)
    summary = session_summary(session)
    normalized = _normalized_denominations(denominations or [])
    if normalized:
        total = money(sum((row[2] for row in normalized), ZERO))
    elif counted_cash is not None:
        total = money(counted_cash)
    else:
        raise ValidationError({"counted_cash": "Ingresa denominaciones o el total contado."})
    if total < 0:
        raise ValidationError({"counted_cash": "El total contado no puede ser negativo."})
    difference = money(total - summary["expected_cash"])
    if difference and len(difference_reason.strip()) < 5:
        raise ValidationError({"difference_reason": "Explica la diferencia antes de guardar el arqueo."})
    fingerprint = movement_fingerprint(session)
    digest = payload_hash({
        "session": session.pk,
        "denominations": [(str(item[0]), item[1]) for item in normalized],
        "counted_cash": str(total), "difference_reason": difference_reason.strip(),
        "movement_fingerprint": fingerprint,
    })
    existing = _idempotent_resource(
        session.organization, idempotency_key, CashIdempotencyOperation.PERFORM_COUNT,
        digest, CashCount, actor,
    )
    if existing:
        return existing, False
    if session.status != CashSessionStatus.OPEN:
        raise ConflictError("El arqueo no puede registrarse porque la caja está cerrada.")
    cash_count = CashCount.objects.create(
        cash_session=session, expected_cash=summary["expected_cash"], counted_cash=total,
        difference=difference, difference_reason=difference_reason.strip()[:2000],
        movement_fingerprint=fingerprint, counted_by=actor,
    )
    CashCountDenomination.objects.bulk_create([
        CashCountDenomination(
            cash_count=cash_count, denomination=denomination,
            quantity=quantity, subtotal=subtotal,
        ) for denomination, quantity, subtotal in normalized
    ])
    _save_idempotency(
        session.organization, idempotency_key, CashIdempotencyOperation.PERFORM_COUNT,
        digest, cash_count, actor,
    )
    audit(
        session.organization, actor, CashAuditEvent.COUNT_PERFORMED,
        f"Arqueo de {session.session_number}: contado L {total:,.2f}, diferencia L {difference:,.2f}.",
        cash_register=session.cash_register, cash_session=session, cash_count=cash_count,
    )
    if difference:
        audit(
            session.organization, actor, CashAuditEvent.DIFFERENCE_DETECTED,
            f"{session.session_number} presenta diferencia de caja de L {difference:,.2f}.",
            cash_register=session.cash_register, cash_session=session, cash_count=cash_count,
        )
    return cash_count, True


@transaction.atomic
def close_cash_session(session, actor, cash_count_id, notes, idempotency_key):
    session = CashSession.objects.select_for_update().select_related(
        "organization", "branch", "cash_register", "cashier"
    ).get(pk=session.pk)
    digest = payload_hash({
        "session": session.pk, "cash_count": cash_count_id, "notes": notes.strip(),
    })
    existing = _idempotent_resource(
        session.organization, idempotency_key, CashIdempotencyOperation.CLOSE_SESSION,
        digest, CashSession, actor,
    )
    if existing:
        return existing, False
    if session.status != CashSessionStatus.OPEN:
        raise ConflictError("Esta sesión ya fue cerrada.")
    _assert_session_actor(session, actor)
    cash_count = CashCount.objects.select_for_update().filter(
        pk=cash_count_id, cash_session=session
    ).prefetch_related("denominations").first()
    if not cash_count:
        raise ValidationError({"cash_count": "Realiza un arqueo válido antes de cerrar."})
    latest_count = session.cash_counts.order_by("-counted_at", "-id").first()
    if latest_count.pk != cash_count.pk:
        raise ConflictError("Existe un arqueo más reciente. Actualiza la información antes de cerrar.")
    current_fingerprint = movement_fingerprint(session)
    if cash_count.movement_fingerprint != current_fingerprint:
        raise ConflictError("La caja cambió mientras realizabas el arqueo. Actualiza la información.")
    summary = session_summary(session)
    if money(cash_count.expected_cash) != summary["expected_cash"]:
        raise ConflictError("La caja cambió mientras realizabas el arqueo. Actualiza la información.")
    if cash_count.difference and len(cash_count.difference_reason.strip()) < 5:
        raise ValidationError({"difference_reason": "La diferencia requiere una observación."})
    session.status = CashSessionStatus.CLOSED
    session.closed_at = timezone.now()
    session.closed_by = actor
    if notes.strip():
        session.notes = f"{session.notes}\nCierre: {notes.strip()}".strip()[:4000]
    session.cash_in_snapshot = summary["cash_in"]
    session.cash_out_snapshot = summary["cash_out"]
    session.expected_cash_snapshot = summary["expected_cash"]
    session.counted_cash_snapshot = cash_count.counted_cash
    session.difference_snapshot = cash_count.difference
    session.method_totals_snapshot = {
        key: str(value) for key, value in summary["method_totals"].items()
    }
    session.save(update_fields=(
        "status", "closed_at", "closed_by", "notes", "cash_in_snapshot",
        "cash_out_snapshot", "expected_cash_snapshot", "counted_cash_snapshot",
        "difference_snapshot", "method_totals_snapshot", "updated_at",
    ))
    _save_idempotency(
        session.organization, idempotency_key, CashIdempotencyOperation.CLOSE_SESSION,
        digest, session, actor,
    )
    audit(
        session.organization, actor, CashAuditEvent.SESSION_CLOSED,
        f"{session.session_number} cerrada. Esperado L {summary['expected_cash']:,.2f}; "
        f"contado L {cash_count.counted_cash:,.2f}; diferencia L {cash_count.difference:,.2f}.",
        cash_register=session.cash_register, cash_session=session, cash_count=cash_count,
    )
    return session, True


def movement_totals(queryset):
    confirmed = queryset.filter(status=CashMovementStatus.CONFIRMED)
    incoming = _sum(confirmed.filter(direction=CashMovementDirection.IN))
    outgoing = _sum(confirmed.filter(direction=CashMovementDirection.OUT))
    cash_in = _sum(confirmed.filter(direction=CashMovementDirection.IN, affects_cash=True))
    cash_out = _sum(confirmed.filter(direction=CashMovementDirection.OUT, affects_cash=True))
    return {
        "total_in": incoming, "total_out": outgoing, "net": money(incoming - outgoing),
        "cash_in": cash_in, "cash_out": cash_out, "cash_net": money(cash_in - cash_out),
    }


def cash_settlements_for_user(user):
    queryset = CollectorSettlement.objects.filter(
        status=SettlementStatus.ACCEPTED,
    ).select_related("organization", "branch", "collector", "work_session")
    if user.is_superuser or role_code(user) == RoleCode.SUPERADMIN:
        return queryset
    queryset = queryset.filter(organization_id=user.organization_id)
    if is_branch_restricted(user) and user.branch_id:
        queryset = queryset.filter(branch_id=user.branch_id)
    return queryset


def pending_settlements_for_user(user):
    return cash_settlements_for_user(user).filter(cash_reception__isnull=True)


def cash_dashboard(user):
    today = timezone.localdate()
    sessions = scope_cash(
        CashSession.objects.select_related("cash_register", "cashier"), user, "view_session"
    )
    movements = scope_cash(
        CashMovement.objects.filter(
            status=CashMovementStatus.CONFIRMED, created_at__date=today
        ), user, "view_session"
    )
    payments = scope_payments(
        Payment.objects.filter(status=PaymentStatus.CONFIRMED, payment_date__date=today), user
    )
    payment_total = _sum(payments)
    payment_methods = {
        method: _sum(payments.filter(payment_method=method)) for method in PaymentMethod.values
    }
    cash_received = _sum(movements.filter(
        direction=CashMovementDirection.IN, affects_cash=True
    ))
    differences = sessions.filter(
        status=CashSessionStatus.CLOSED, closed_at__date=today
    ).aggregate(value=Coalesce(Sum("difference_snapshot"), ZERO))["value"]
    pending = pending_settlements_for_user(user)
    return {
        "payment_total_today": payment_total,
        "payment_methods": payment_methods,
        "cash_received_today": cash_received,
        "open_sessions": sessions.filter(status=CashSessionStatus.OPEN).count(),
        "closed_sessions_today": sessions.filter(
            status=CashSessionStatus.CLOSED, closed_at__date=today
        ).count(),
        "cash_differences_today": money(differences or ZERO),
        "pending_settlements": pending.count(),
        "pending_settlement_cash": _sum(pending, "reported_cash"),
    }
