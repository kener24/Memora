import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import RoleCode
from contracts.choices import ContractActivityAction, ContractStatus, IdempotencyOperation
from contracts.exceptions import ConflictError
from contracts.models import Contract, ContractIdempotencyKey
from contracts.services import record_contract_activity
from installments.choices import InstallmentStatus, ScheduleStatus
from installments.models import Installment

from .choices import FinancialStatus, PaymentMethod, PaymentStatus, PaymentType, ReceiptStatus
from .models import Payment, PaymentApplication, PaymentSequence, Receipt, ReceiptSequence


CENT = Decimal("0.01")
REFERENCE_METHODS = {PaymentMethod.TRANSFER, PaymentMethod.CARD, PaymentMethod.CHECK}


def money(value):
    try:
        return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({"amount": "Ingresa un monto monetario válido."}) from exc


def allocate_payment_number(organization):
    sequence, _ = PaymentSequence.objects.get_or_create(organization=organization)
    PaymentSequence.objects.filter(pk=sequence.pk).update(next_value=F("next_value") + 1)
    sequence.refresh_from_db(fields=("next_value",))
    return f"PAG-{sequence.next_value - 1:06d}"


def allocate_receipt_number(organization):
    sequence, _ = ReceiptSequence.objects.get_or_create(organization=organization)
    ReceiptSequence.objects.filter(pk=sequence.pk).update(next_value=F("next_value") + 1)
    sequence.refresh_from_db(fields=("next_value",))
    return f"REC-{sequence.next_value - 1:06d}"


def confirmed_payments(contract):
    return Payment.objects.filter(contract=contract, status=PaymentStatus.CONFIRMED)


def financial_summary(contract):
    cached = getattr(contract, "_payment_financial_summary", None)
    if cached is not None:
        return cached
    aggregates = confirmed_payments(contract).aggregate(
        total=Sum("amount"), initial=Sum("initial_amount_applied"), direct=Sum("direct_amount_applied")
    )
    installment_paid = PaymentApplication.objects.filter(
        payment__contract=contract, payment__status=PaymentStatus.CONFIRMED
    ).aggregate(value=Sum("amount_applied"))["value"] or Decimal("0.00")
    total_paid = money(aggregates["total"] or 0)
    initial_paid = money(aggregates["initial"] or 0)
    direct_paid = money(aggregates["direct"] or 0)
    installment_paid = money(installment_paid)
    balance = max(money(contract.total_price) - total_paid, Decimal("0.00"))
    initial_pending = max(money(contract.initial_payment_agreed) - initial_paid, Decimal("0.00"))
    financed_pending = max(money(contract.financed_amount) - installment_paid, Decimal("0.00"))
    if total_paid <= 0:
        status = FinancialStatus.UNPAID
    elif balance <= 0:
        status = FinancialStatus.PAID
    else:
        status = FinancialStatus.PARTIAL
    cached = {
        "total_price": money(contract.total_price), "total_paid": total_paid,
        "contract_balance": balance, "financial_status": status,
        "financial_status_label": dict(FinancialStatus.choices)[status],
        "initial_payment_agreed": money(contract.initial_payment_agreed),
        "initial_payment_paid": initial_paid, "initial_payment_pending": initial_pending,
        "financed_amount": money(contract.financed_amount),
        "financed_paid": installment_paid, "financed_pending": financed_pending,
        "direct_paid": direct_paid,
    }
    contract._payment_financial_summary = cached
    return cached


def customer_financial_summary(customer):
    active_contracts = Contract.objects.filter(customer=customer, status=ContractStatus.ACTIVE)
    summaries = [financial_summary(item) for item in active_contracts]
    last_payment = Payment.objects.filter(
        customer=customer, status=PaymentStatus.CONFIRMED
    ).order_by("-payment_date", "-created_at", "-id").first()
    return {
        "active_contracts": len(summaries),
        "total_balance": sum((item["contract_balance"] for item in summaries), Decimal("0.00")),
        "last_payment": {
            "id": last_payment.pk, "payment_number": last_payment.payment_number,
            "amount": last_payment.amount, "payment_date": last_payment.payment_date,
        } if last_payment else None,
    }


@dataclass(frozen=True)
class AllocationLine:
    installment: Installment
    amount: Decimal


@dataclass(frozen=True)
class AllocationPreview:
    amount: Decimal
    balance_before: Decimal
    balance_after: Decimal
    initial_amount: Decimal
    direct_amount: Decimal
    applications: tuple[AllocationLine, ...]


def active_installments(contract, lock=False):
    queryset = Installment.objects.filter(
        contract=contract, schedule__status=ScheduleStatus.ACTIVE
    ).exclude(status=InstallmentStatus.CANCELLED).select_related("schedule").order_by(
        "due_date", "installment_number", "id"
    )
    return queryset.select_for_update() if lock else queryset


def _allocate_to_installments(amount, installments):
    remaining = money(amount)
    lines = []
    for installment in installments:
        pending = max(money(installment.current_amount) - money(installment.paid_amount), Decimal("0.00"))
        if pending <= 0:
            continue
        applied = min(remaining, pending)
        if applied > 0:
            lines.append(AllocationLine(installment, applied))
            remaining = money(remaining - applied)
        if remaining <= 0:
            break
    return tuple(lines), remaining


def preview_allocation(contract, amount, payment_type):
    amount = money(amount)
    if amount <= 0:
        raise ValidationError({"amount": "El monto debe ser mayor que cero."})
    if contract.status != ContractStatus.ACTIVE:
        raise ValidationError({"contract": "El contrato está cancelado o no se encuentra activo."})
    summary = financial_summary(contract)
    if amount > summary["contract_balance"]:
        raise ValidationError({"amount": "El monto excede el saldo pendiente del contrato."})
    installments = list(active_installments(contract))
    if contract.allow_financing and contract.financed_amount > 0 and not installments and payment_type in {
        PaymentType.INSTALLMENT, PaymentType.ADVANCE, PaymentType.SETTLEMENT,
    }:
        raise ValidationError({"schedule": "Genera el calendario de cuotas antes de registrar este pago."})

    initial_amount = Decimal("0.00")
    direct_amount = Decimal("0.00")
    applications = ()
    if payment_type == PaymentType.INITIAL_PAYMENT:
        if amount > summary["initial_payment_pending"]:
            raise ValidationError({"amount": "El monto excede la prima pendiente."})
        initial_amount = amount
    elif payment_type in {PaymentType.INSTALLMENT, PaymentType.ADVANCE}:
        applications, remaining = _allocate_to_installments(amount, installments)
        if remaining > 0:
            raise ValidationError({"amount": "El monto excede el saldo financiado pendiente."})
    elif payment_type == PaymentType.SETTLEMENT:
        if amount != summary["contract_balance"]:
            raise ConflictError("El monto de liquidación debe coincidir con el saldo actual del contrato.")
        initial_amount = min(amount, summary["initial_payment_pending"])
        remaining = money(amount - initial_amount)
        applications, remaining = _allocate_to_installments(remaining, installments)
        direct_amount = remaining
    elif payment_type == PaymentType.OTHER:
        installment_pending = sum(
            (max(money(item.current_amount) - money(item.paid_amount), Decimal("0.00")) for item in installments),
            Decimal("0.00"),
        )
        direct_available = max(
            summary["contract_balance"] - summary["initial_payment_pending"] - installment_pending,
            Decimal("0.00"),
        )
        if amount > direct_available:
            raise ValidationError({"payment_type": "Este monto debe registrarse como prima, cuota o liquidación."})
        direct_amount = amount
    else:
        raise ValidationError({"payment_type": "Selecciona un tipo de pago válido."})

    assigned = initial_amount + direct_amount + sum((line.amount for line in applications), Decimal("0.00"))
    if money(assigned) != amount:
        raise ValidationError({"amount": "El monto no puede asignarse completamente a obligaciones válidas."})
    return AllocationPreview(
        amount=amount, balance_before=summary["contract_balance"],
        balance_after=money(summary["contract_balance"] - amount),
        initial_amount=money(initial_amount), direct_amount=money(direct_amount), applications=applications,
    )


def payload_digest(contract, payload):
    normalized = {
        "contract": contract.pk, "amount": str(money(payload.get("amount"))),
        "payment_type": payload.get("payment_type"), "payment_method": payload.get("payment_method"),
        "reference": (payload.get("reference") or "").strip(), "notes": (payload.get("notes") or "").strip(),
        "payment_date": payload.get("payment_date").isoformat() if payload.get("payment_date") else None,
    }
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _status_for_installment(installment):
    if installment.paid_amount >= installment.current_amount:
        return InstallmentStatus.PAID
    if installment.paid_amount > 0:
        return InstallmentStatus.PARTIALLY_PAID
    return InstallmentStatus.OVERDUE if installment.due_date < timezone.localdate() else InstallmentStatus.PENDING


def _apply_lines(payment, lines):
    applications = []
    for line in lines:
        installment = line.installment
        installment.paid_amount = money(installment.paid_amount + line.amount)
        installment.status = _status_for_installment(installment)
        installment.save(update_fields=("paid_amount", "status", "updated_at"))
        applications.append(PaymentApplication(
            payment=payment, installment=installment, amount_applied=line.amount
        ))
    PaymentApplication.objects.bulk_create(applications)


def _receipt_snapshot(payment, preview):
    contract = payment.contract
    customer = payment.customer
    organization = payment.organization
    receiver = payment.received_by.get_full_name().strip() or payment.received_by.username
    applications = []
    if preview.initial_amount:
        applications.append({"kind": "initial_payment", "label": "Prima contractual", "amount": str(preview.initial_amount)})
    applications.extend({
        "kind": "installment", "installment_id": line.installment.pk,
        "installment_number": line.installment.installment_number,
        "due_date": line.installment.due_date.isoformat(), "amount": str(line.amount),
    } for line in preview.applications)
    if preview.direct_amount:
        applications.append({"kind": "direct", "label": "Saldo contractual", "amount": str(preview.direct_amount)})
    return Receipt.objects.create(
        organization=organization, branch=payment.branch,
        receipt_number=allocate_receipt_number(organization), payment=payment,
        organization_name_snapshot=organization.name,
        organization_address_snapshot=organization.address,
        organization_phone_snapshot=organization.phone,
        customer_name_snapshot=contract.customer_name_snapshot or customer.full_name,
        customer_code_snapshot=customer.customer_code,
        customer_identity_snapshot=contract.customer_identity_snapshot or customer.identity_number or "",
        contract_number_snapshot=contract.contract_number,
        concept_snapshot=payment.get_payment_type_display(),
        method_snapshot=payment.get_payment_method_display(),
        reference_snapshot=payment.reference, received_by_snapshot=receiver,
        amount_snapshot=payment.amount, balance_before=preview.balance_before,
        balance_after=preview.balance_after, applications_snapshot=applications,
    )


@transaction.atomic
def register_payment(contract, user, payload, idempotency_key, *, can_backdate=False):
    contract = Contract.objects.select_for_update().select_related(
        "organization", "branch", "customer"
    ).get(pk=contract.pk)
    digest = payload_digest(contract, payload)
    existing_key = ContractIdempotencyKey.objects.select_for_update().filter(
        organization=contract.organization, key=idempotency_key
    ).first()
    if existing_key:
        if (
            existing_key.operation == IdempotencyOperation.PAYMENT_CREATE
            and existing_key.payload_hash == digest and existing_key.resource_type == "payment"
            and existing_key.resource_id
        ):
            return Payment.objects.get(pk=existing_key.resource_id), False
        raise ConflictError("Esta clave de idempotencia fue utilizada con datos diferentes u otra operación.")

    payment_date = payload.get("payment_date") or timezone.now()
    if payment_date > timezone.now():
        raise ValidationError({"payment_date": "La fecha del pago no puede estar en el futuro."})
    if timezone.localtime(payment_date).date() < timezone.localdate() and not can_backdate:
        raise ValidationError({"payment_date": "No tienes permiso para registrar pagos retroactivos."})
    method = payload["payment_method"]
    reference = (payload.get("reference") or "").strip()
    if method in REFERENCE_METHODS and not reference:
        raise ValidationError({"reference": "La referencia es obligatoria para este método de pago."})

    collector_session = None
    if getattr(getattr(user, "role", None), "code", None) == RoleCode.COLLECTOR:
        from collection_management.choices import AssignmentStatus, WorkSessionStatus
        from collection_management.models import CollectionAssignment, CollectorWorkSession

        collector_session = CollectorWorkSession.objects.select_for_update().filter(
            collector=user, organization=contract.organization, branch=contract.branch,
            status=WorkSessionStatus.OPEN,
        ).first()
        if not collector_session:
            raise ValidationError({"work_session": "No tienes una jornada abierta."})
        if not CollectionAssignment.objects.filter(
            contract=contract, collector=user, status=AssignmentStatus.ACTIVE,
        ).exists():
            raise ValidationError({"contract": "No puedes cobrar un contrato que no está asignado a tu cartera."})

    preview = preview_allocation(contract, payload["amount"], payload["payment_type"])
    payment = Payment.objects.create(
        organization=contract.organization, branch=contract.branch, contract=contract,
        customer=contract.customer, payment_number=allocate_payment_number(contract.organization),
        payment_date=payment_date, amount=preview.amount, payment_method=method,
        reference=reference, payment_type=payload["payment_type"], notes=(payload.get("notes") or "").strip(),
        received_by=user, created_by=user, idempotency_key=idempotency_key,
        initial_amount_applied=preview.initial_amount, direct_amount_applied=preview.direct_amount,
        collector_session=collector_session,
    )
    _apply_lines(payment, preview.applications)
    receipt = _receipt_snapshot(payment, preview)
    record_contract_activity(
        contract, user, ContractActivityAction.PAYMENT_CREATED,
        f"Se registró {payment.payment_number} por L {payment.amount:,.2f}.",
    )
    if payment.payment_type == PaymentType.INITIAL_PAYMENT:
        record_contract_activity(contract, user, ContractActivityAction.INITIAL_PAYMENT_REGISTERED, "Se aplicó el pago a la prima contractual.")
    if preview.applications:
        record_contract_activity(
            contract, user, ContractActivityAction.PAYMENT_APPLIED,
            f"El pago se distribuyó en {len(preview.applications)} cuota(s) por orden de vencimiento.",
        )
    if payment.payment_type == PaymentType.SETTLEMENT:
        record_contract_activity(contract, user, ContractActivityAction.SETTLEMENT_REGISTERED, "Se liquidó el saldo contractual pendiente.")
    record_contract_activity(
        contract, user, ContractActivityAction.RECEIPT_ISSUED,
        f"Se emitió el recibo {receipt.receipt_number}.",
    )
    ContractIdempotencyKey.objects.create(
        organization=contract.organization, key=idempotency_key,
        operation=IdempotencyOperation.PAYMENT_CREATE, contract=contract, user=user,
        payload_hash=digest, resource_type="payment", resource_id=payment.pk, response_status=201,
    )
    return payment, True


def preview_data(preview):
    return {
        "amount": preview.amount, "balance_before": preview.balance_before,
        "balance_after": preview.balance_after, "initial_amount": preview.initial_amount,
        "direct_amount": preview.direct_amount,
        "applications": [{
            "installment_id": line.installment.pk,
            "installment_number": line.installment.installment_number,
            "due_date": line.installment.due_date, "amount": line.amount,
        } for line in preview.applications],
    }


@transaction.atomic
def rebuild_contract_payment_allocations(contract, user=None):
    contract = Contract.objects.select_for_update().get(pk=contract.pk)
    installments = list(active_installments(contract, lock=True))
    payments = list(Payment.objects.select_for_update().filter(
        contract=contract, status=PaymentStatus.CONFIRMED
    ).order_by("payment_date", "created_at", "id"))
    PaymentApplication.objects.filter(payment__in=payments).delete()
    rebuilt_at = timezone.now()
    for item in installments:
        item.paid_amount = Decimal("0.00")
        item.status = InstallmentStatus.OVERDUE if item.due_date < timezone.localdate() else InstallmentStatus.PENDING
        item.updated_at = rebuilt_at
    Installment.objects.bulk_update(installments, ("paid_amount", "status", "updated_at"))

    initial_remaining = money(contract.initial_payment_agreed)
    direct_capacity = max(
        money(contract.total_price) - money(contract.initial_payment_agreed) - money(contract.financed_amount),
        Decimal("0.00"),
    )
    for payment in payments:
        initial = Decimal("0.00")
        direct = Decimal("0.00")
        amount_remaining = money(payment.amount)
        if payment.payment_type == PaymentType.INITIAL_PAYMENT:
            initial = min(amount_remaining, initial_remaining)
            amount_remaining = money(amount_remaining - initial)
        elif payment.payment_type == PaymentType.SETTLEMENT:
            initial = min(amount_remaining, initial_remaining)
            amount_remaining = money(amount_remaining - initial)
        if payment.payment_type in {PaymentType.INSTALLMENT, PaymentType.ADVANCE, PaymentType.SETTLEMENT}:
            lines, amount_remaining = _allocate_to_installments(amount_remaining, installments)
            _apply_lines(payment, lines)
        if payment.payment_type in {PaymentType.SETTLEMENT, PaymentType.OTHER} and amount_remaining > 0:
            direct = min(amount_remaining, direct_capacity)
            direct_capacity = money(direct_capacity - direct)
            amount_remaining = money(amount_remaining - direct)
        if amount_remaining > 0:
            raise ValidationError({"payment": f"No fue posible reconstruir completamente {payment.payment_number}."})
        initial_remaining = money(initial_remaining - initial)
        payment.initial_amount_applied = initial
        payment.direct_amount_applied = direct
        payment.save(update_fields=("initial_amount_applied", "direct_amount_applied", "updated_at"))
    if user:
        record_contract_activity(
            contract, user, ContractActivityAction.PAYMENT_ALLOCATIONS_REBUILT,
            "Se reconstruyeron determinísticamente las aplicaciones por fecha, creación e ID.",
        )


@transaction.atomic
def void_payment(payment, user, reason):
    payment = Payment.objects.select_for_update().select_related("contract", "receipt").get(pk=payment.pk)
    if payment.status == PaymentStatus.VOIDED:
        raise ConflictError("Este pago ya fue anulado.")
    payment.status = PaymentStatus.VOIDED
    payment.voided_at = timezone.now()
    payment.voided_by = user
    payment.void_reason = reason
    payment.save(update_fields=("status", "voided_at", "voided_by", "void_reason", "updated_at"))
    receipt = payment.receipt
    receipt.status = ReceiptStatus.VOIDED
    receipt.save(update_fields=("status", "updated_at"))
    rebuild_contract_payment_allocations(payment.contract, user)
    record_contract_activity(
        payment.contract, user, ContractActivityAction.PAYMENT_VOIDED,
        f"Se anuló {payment.payment_number}. Motivo: {reason[:150]}",
    )
    settlement_item = getattr(payment, "collector_settlement_item", None)
    if settlement_item:
        from collection_management.choices import OperationsAuditEvent
        from collection_management.models import CollectionOperationsAudit

        CollectionOperationsAudit.objects.create(
            organization=payment.organization, actor=user,
            event=OperationsAuditEvent.SETTLED_PAYMENT_VOIDED,
            description=(
                f"{payment.payment_number} fue anulado después de incluirse en "
                f"{settlement_item.settlement.settlement_number}. Motivo: {reason[:300]}"
            ),
            settlement=settlement_item.settlement, payment=payment,
        )
    return payment
