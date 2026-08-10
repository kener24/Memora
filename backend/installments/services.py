import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from contracts.choices import ContractActivityAction, ContractStatus, PaymentFrequency
from contracts.models import Contract
from contracts.services import record_contract_activity

from .choices import InstallmentStatus, ScheduleStatus
from .models import Installment, InstallmentSchedule


CENT = Decimal("0.01")
MAX_INSTALLMENTS = 5200


@dataclass(frozen=True)
class ScheduleItemValue:
    installment_number: int
    due_date: date
    amount: Decimal


@dataclass(frozen=True)
class SchedulePreview:
    total: Decimal
    frequency: str
    regular_installment_amount: Decimal
    first_due_date: date
    last_due_date: date
    total_installments: int
    items: tuple[ScheduleItemValue, ...]


def money(value):
    try:
        return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError({"amount": "Ingresa un importe monetario válido."}) from exc


def monthly_due_date(first_due_date, offset):
    month_index = first_due_date.month - 1 + offset
    year = first_due_date.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(first_due_date.day, last_day))


def due_date_for(first_due_date, frequency, offset):
    if frequency == PaymentFrequency.MONTHLY:
        return monthly_due_date(first_due_date, offset)
    if frequency == PaymentFrequency.BIWEEKLY:
        return first_due_date + timedelta(days=15 * offset)
    if frequency == PaymentFrequency.WEEKLY:
        return first_due_date + timedelta(days=7 * offset)
    raise ValidationError({"frequency": "El calendario personalizado requiere cuotas manuales."})


def _validate_first_due(contract, first_due_date):
    if not first_due_date:
        raise ValidationError({"first_due_date": "Selecciona el primer vencimiento."})
    if first_due_date < contract.sale_date:
        raise ValidationError({
            "first_due_date": "El primer vencimiento no puede ser anterior a la fecha de venta."
        })


def build_automatic_preview(contract, frequency, installment_amount, first_due_date):
    total = money(contract.financed_amount)
    regular = money(installment_amount)
    if total <= 0:
        raise ValidationError({"contract": "Este contrato no posee financiamiento."})
    if regular <= 0:
        raise ValidationError({"installment_amount": "El monto de la cuota debe ser mayor que cero."})
    if frequency not in {
        PaymentFrequency.MONTHLY, PaymentFrequency.BIWEEKLY, PaymentFrequency.WEEKLY,
    }:
        raise ValidationError({"frequency": "Selecciona una frecuencia automática válida."})
    _validate_first_due(contract, first_due_date)
    items = []
    remaining = total
    number = 1
    while remaining > 0:
        if number > MAX_INSTALLMENTS:
            raise ValidationError({
                "installment_amount": "La cuota produciría demasiadas obligaciones. Aumenta el importe."
            })
        amount = min(regular, remaining).quantize(CENT)
        items.append(ScheduleItemValue(number, due_date_for(first_due_date, frequency, number - 1), amount))
        remaining = (remaining - amount).quantize(CENT)
        number += 1
    return SchedulePreview(
        total=total, frequency=frequency, regular_installment_amount=regular,
        first_due_date=items[0].due_date, last_due_date=items[-1].due_date,
        total_installments=len(items), items=tuple(items),
    )


def build_manual_preview(contract, manual_installments):
    total = money(contract.financed_amount)
    if total <= 0:
        raise ValidationError({"contract": "Este contrato no posee financiamiento."})
    if not manual_installments:
        raise ValidationError({"manual_installments": "Agrega al menos una cuota manual."})
    if len(manual_installments) > MAX_INSTALLMENTS:
        raise ValidationError({"manual_installments": "El calendario supera el máximo permitido."})
    normalized = []
    for index, item in enumerate(manual_installments):
        due_date = item.get("due_date")
        amount = money(item.get("amount"))
        if not due_date:
            raise ValidationError({"manual_installments": f"La cuota {index + 1} requiere fecha."})
        if due_date < contract.sale_date:
            raise ValidationError({
                "manual_installments": f"La fecha de la cuota {index + 1} es anterior a la venta."
            })
        if amount <= 0:
            raise ValidationError({
                "manual_installments": f"El importe de la cuota {index + 1} debe ser mayor que cero."
            })
        normalized.append((due_date, index, amount))
    normalized.sort(key=lambda value: (value[0], value[1]))
    item_total = sum((item[2] for item in normalized), Decimal("0.00")).quantize(CENT)
    if item_total != total:
        raise ValidationError({
            "manual_installments": f"Las cuotas manuales deben sumar exactamente L {total:,.2f}."
        })
    items = tuple(
        ScheduleItemValue(number, item[0], item[2])
        for number, item in enumerate(normalized, start=1)
    )
    return SchedulePreview(
        total=total, frequency=PaymentFrequency.CUSTOM,
        regular_installment_amount=items[0].amount, first_due_date=items[0].due_date,
        last_due_date=items[-1].due_date, total_installments=len(items), items=items,
    )


def build_preview(contract, *, frequency, installment_amount=None, first_due_date=None, manual_installments=None):
    if frequency == PaymentFrequency.CUSTOM:
        return build_manual_preview(contract, manual_installments or [])
    return build_automatic_preview(contract, frequency, installment_amount, first_due_date)


def effective_installment_status(installment, as_of=None):
    if installment.status == InstallmentStatus.CANCELLED:
        return InstallmentStatus.CANCELLED
    if installment.paid_amount >= installment.current_amount:
        return InstallmentStatus.PAID
    if installment.paid_amount > 0:
        return InstallmentStatus.PARTIALLY_PAID
    today = as_of or timezone.localdate()
    if installment.due_date < today and installment.pending_amount > 0:
        return InstallmentStatus.OVERDUE
    return InstallmentStatus.PENDING


def _persist_schedule(contract, preview, user, *, version, previous=None, reason=""):
    now = timezone.now()
    schedule = InstallmentSchedule.objects.create(
        organization=contract.organization, branch=contract.branch, contract=contract,
        previous_schedule=previous, version=version, status=ScheduleStatus.ACTIVE,
        total_financed=preview.total, regular_installment_amount=preview.regular_installment_amount,
        frequency=preview.frequency, first_due_date=preview.first_due_date,
        last_due_date=preview.last_due_date, total_installments=preview.total_installments,
        generated_by=user, generated_at=now, reprogramming_reason=reason,
        reprogrammed_by=user if previous else None, reprogrammed_at=now if previous else None,
    )
    Installment.objects.bulk_create([
        Installment(
            organization=contract.organization, branch=contract.branch, contract=contract,
            schedule=schedule, installment_number=item.installment_number, due_date=item.due_date,
            original_amount=item.amount, current_amount=item.amount, paid_amount=Decimal("0.00"),
            status=InstallmentStatus.PENDING, generated_at=now,
        )
        for item in preview.items
    ])
    return schedule


@transaction.atomic
def generate_schedule(contract, user, *, manual_installments=None):
    contract = Contract.objects.select_for_update().get(pk=contract.pk)
    existing = InstallmentSchedule.objects.filter(
        contract=contract, status=ScheduleStatus.ACTIVE
    ).prefetch_related("installments").first()
    if existing:
        return existing, False
    if contract.status != ContractStatus.ACTIVE:
        raise ValidationError({"contract": "Solo contratos activos pueden generar cuotas."})
    if not contract.allow_financing or contract.financed_amount <= 0:
        raise ValidationError({"contract": "Este contrato no posee financiamiento."})
    preview = build_preview(
        contract, frequency=contract.payment_frequency,
        installment_amount=contract.installment_amount, first_due_date=contract.first_due_date,
        manual_installments=manual_installments,
    )
    version = (InstallmentSchedule.objects.filter(contract=contract).aggregate(value=Max("version"))["value"] or 0) + 1
    schedule = _persist_schedule(contract, preview, user, version=version)
    record_contract_activity(
        contract, user, ContractActivityAction.SCHEDULE_GENERATED,
        f"Se generó el calendario v{version} con {preview.total_installments} cuotas.",
    )
    return schedule, True


@transaction.atomic
def reprogram_schedule(contract, user, *, frequency, installment_amount=None, first_due_date=None,
                       manual_installments=None, reason):
    contract = Contract.objects.select_for_update().get(pk=contract.pk)
    if contract.status != ContractStatus.ACTIVE:
        raise ValidationError({"contract": "Solo contratos activos pueden reprogramarse."})
    previous = InstallmentSchedule.objects.select_for_update().filter(
        contract=contract, status=ScheduleStatus.ACTIVE
    ).first()
    if not previous:
        raise ValidationError({"schedule": "Este contrato todavía no posee un calendario activo."})
    if contract.payments.filter(status="confirmed").exists():
        raise ValidationError({
            "schedule": "Este contrato ya tiene pagos registrados y requiere un ajuste financiero controlado."
        })
    if previous.installments.filter(paid_amount__gt=0).exists():
        raise ValidationError({"schedule": "No se puede reprogramar un calendario con pagos aplicados."})
    preview = build_preview(
        contract, frequency=frequency, installment_amount=installment_amount,
        first_due_date=first_due_date, manual_installments=manual_installments,
    )
    previous.status = ScheduleStatus.REPLACED
    previous.save(update_fields=("status", "updated_at"))
    previous.installments.exclude(status=InstallmentStatus.CANCELLED).update(
        status=InstallmentStatus.CANCELLED, updated_at=timezone.now()
    )
    version = previous.version + 1
    schedule = _persist_schedule(
        contract, preview, user, version=version, previous=previous, reason=reason,
    )
    record_contract_activity(
        contract, user, ContractActivityAction.SCHEDULE_REPROGRAMMED,
        f"Se reemplazó el calendario v{previous.version} por v{version}. Motivo: {reason[:120]}",
    )
    return schedule


@transaction.atomic
def cancel_contract_schedule(contract, user):
    schedule = InstallmentSchedule.objects.select_for_update().filter(
        contract=contract, status=ScheduleStatus.ACTIVE
    ).first()
    if not schedule:
        return None
    schedule.status = ScheduleStatus.CANCELLED
    schedule.save(update_fields=("status", "updated_at"))
    schedule.installments.exclude(status=InstallmentStatus.CANCELLED).update(
        status=InstallmentStatus.CANCELLED, updated_at=timezone.now()
    )
    record_contract_activity(
        contract, user, ContractActivityAction.SCHEDULE_CANCELLED,
        f"El calendario v{schedule.version} y sus obligaciones quedaron cancelados.",
    )
    return schedule
