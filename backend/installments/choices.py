from django.db import models


class ScheduleStatus(models.TextChoices):
    ACTIVE = "active", "Activo"
    REPLACED = "replaced", "Reemplazado"
    CANCELLED = "cancelled", "Cancelado"


class InstallmentStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    PARTIALLY_PAID = "partially_paid", "Pago parcial"
    PAID = "paid", "Pagada"
    OVERDUE = "overdue", "Vencida"
    CANCELLED = "cancelled", "Cancelada"
