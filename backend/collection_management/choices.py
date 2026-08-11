from django.db import models


DUE_SOON_DAYS = 7
SEVERE_OVERDUE_DAYS = 90
RECENT_PAYMENT_DAYS = 30
PROMISE_PAYMENT_GRACE_DAYS = 3

AGING_BUCKETS = (
    ("1_30", "1–30 días", 1, 30),
    ("31_60", "31–60 días", 31, 60),
    ("61_90", "61–90 días", 61, 90),
    ("91_120", "91–120 días", 91, 120),
    ("over_120", "Más de 120 días", 121, None),
)


class CollectionStatus(models.TextChoices):
    CURRENT = "current", "Al día"
    DUE_SOON = "due_soon", "Próximo a vencer"
    OVERDUE = "overdue", "En mora"
    SEVERELY_OVERDUE = "severely_overdue", "Mora crítica"
    PAID = "paid", "Pagado"


class CollectionPriority(models.TextChoices):
    LOW = "low", "Baja"
    MEDIUM = "medium", "Media"
    HIGH = "high", "Alta"
    CRITICAL = "critical", "Crítica"


class CollectionActionType(models.TextChoices):
    PHONE_CALL = "phone_call", "Llamada"
    WHATSAPP = "whatsapp", "WhatsApp"
    VISIT = "visit", "Visita"
    SMS = "sms", "SMS"
    EMAIL = "email", "Correo"
    OTHER = "other", "Otro"


class CollectionOutcome(models.TextChoices):
    CONTACTED = "contacted", "Contactado"
    NO_ANSWER = "no_answer", "No respondió"
    PROMISE_TO_PAY = "promise_to_pay", "Promesa de pago"
    WRONG_NUMBER = "wrong_number", "Número incorrecto"
    NOT_FOUND = "not_found", "No localizado"
    REFUSED = "refused", "Se negó"
    OTHER = "other", "Otro"


class CollectionActionStatus(models.TextChoices):
    ACTIVE = "active", "Activa"
    VOIDED = "voided", "Anulada"


class PromiseStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    FULFILLED = "fulfilled", "Cumplida"
    BROKEN = "broken", "Incumplida"
    CANCELLED = "cancelled", "Cancelada"


class AuditEvent(models.TextChoices):
    ACTION_CREATED = "action_created", "Gestión creada"
    ACTION_VOIDED = "action_voided", "Gestión anulada"
    PROMISE_CREATED = "promise_created", "Promesa creada"
    PROMISE_FULFILLED = "promise_fulfilled", "Promesa cumplida"
    PROMISE_BROKEN = "promise_broken", "Promesa incumplida"
    PROMISE_CANCELLED = "promise_cancelled", "Promesa cancelada"
