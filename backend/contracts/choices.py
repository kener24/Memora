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


class IdempotencyOperation(models.TextChoices):
    CREATE = "create", "Crear borrador"
    CONFIRM = "confirm", "Confirmar contrato"
