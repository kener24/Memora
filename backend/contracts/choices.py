from django.db import models


class ContractStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    ACTIVE = "active", "Activo"
    CANCELLED = "cancelled", "Cancelado"
    COMPLETED = "completed", "Completado"


class PaymentFrequency(models.TextChoices):
    WEEKLY = "weekly", "Semanal"
    BIWEEKLY = "biweekly", "Quincenal"
    MONTHLY = "monthly", "Mensual"
    CUSTOM = "custom", "Personalizada"


class ContractActivityAction(models.TextChoices):
    DRAFT_CREATED = "draft_created", "Borrador creado"
    DRAFT_UPDATED = "draft_updated", "Borrador actualizado"
    CONFIRMED = "confirmed", "Contrato confirmado"
    CANCELLED = "cancelled", "Contrato cancelado"
    PDF_GENERATED = "pdf_generated", "PDF generado"
    SCHEDULE_GENERATED = "schedule_generated", "Calendario generado"
    SCHEDULE_REPROGRAMMED = "schedule_reprogrammed", "Calendario reprogramado"
    SCHEDULE_CANCELLED = "schedule_cancelled", "Calendario cancelado"
    SCHEDULE_PDF_GENERATED = "schedule_pdf_generated", "Plan de pagos generado"
    PAYMENT_CREATED = "payment_created", "Pago registrado"
    INITIAL_PAYMENT_REGISTERED = "initial_payment_registered", "Prima pagada"
    PAYMENT_APPLIED = "payment_applied", "Pago aplicado"
    SETTLEMENT_REGISTERED = "settlement_registered", "Contrato liquidado"
    RECEIPT_ISSUED = "receipt_issued", "Recibo emitido"
    PAYMENT_VOIDED = "payment_voided", "Pago anulado"
    PAYMENT_ALLOCATIONS_REBUILT = "allocations_rebuilt", "Aplicaciones reconstruidas"


class IdempotencyOperation(models.TextChoices):
    CREATE = "create", "Crear borrador"
    CONFIRM = "confirm", "Confirmar contrato"
    PAYMENT_CREATE = "payment_create", "Registrar pago"
