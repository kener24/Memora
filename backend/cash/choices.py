from django.db import models


class CashSessionStatus(models.TextChoices):
    OPEN = "open", "Abierta"
    CLOSED = "closed", "Cerrada"
    CANCELLED = "cancelled", "Cancelada"


class CashMovementStatus(models.TextChoices):
    CONFIRMED = "confirmed", "Confirmado"
    VOIDED = "voided", "Anulado"


class CashMovementDirection(models.TextChoices):
    IN = "in", "Entrada"
    OUT = "out", "Salida"


class CashMovementType(models.TextChoices):
    CUSTOMER_PAYMENT = "customer_payment", "Pago de cliente"
    COLLECTOR_SETTLEMENT = "collector_settlement", "Liquidación de cobrador"
    MANUAL_INCOME = "manual_income", "Ingreso manual"
    EXPENSE = "expense", "Egreso"
    CASH_ADJUSTMENT = "cash_adjustment", "Ajuste de caja"
    OTHER = "other", "Otro"


class CashMovementCategory(models.TextChoices):
    CUSTOMER_PAYMENT = "customer_payment", "Pago de cliente"
    COLLECTOR_SETTLEMENT = "collector_settlement", "Liquidación de cobrador"
    EXTRAORDINARY_INCOME = "extraordinary_income", "Ingreso extraordinario"
    TEMPORARY_CONTRIBUTION = "temporary_contribution", "Aporte temporal"
    OTHER_INCOME = "other_income", "Otro ingreso"
    OPERATING_EXPENSE = "operating_expense", "Gasto operativo"
    MINOR_PURCHASE = "minor_purchase", "Compra menor"
    AUTHORIZED_REFUND = "authorized_refund", "Devolución autorizada"
    OTHER_EXPENSE = "other_expense", "Otro egreso"


class CashReceptionStatus(models.TextChoices):
    CONFIRMED = "confirmed", "Confirmada"


class CashIdempotencyOperation(models.TextChoices):
    OPEN_SESSION = "open_session", "Abrir sesión"
    CREATE_INCOME = "create_income", "Crear ingreso"
    CREATE_EXPENSE = "create_expense", "Crear egreso"
    RECEIVE_SETTLEMENT = "receive_settlement", "Recibir liquidación"
    PERFORM_COUNT = "perform_count", "Realizar arqueo"
    CLOSE_SESSION = "close_session", "Cerrar sesión"


class CashAuditEvent(models.TextChoices):
    REGISTER_CREATED = "register_created", "Caja creada"
    REGISTER_UPDATED = "register_updated", "Caja actualizada"
    REGISTER_ACTIVATED = "register_activated", "Caja activada"
    REGISTER_DEACTIVATED = "register_deactivated", "Caja inactivada"
    SESSION_OPENED = "session_opened", "Sesión abierta"
    MOVEMENT_CREATED = "movement_created", "Movimiento creado"
    MOVEMENT_VOIDED = "movement_voided", "Movimiento anulado"
    SETTLEMENT_RECEIVED = "settlement_received", "Liquidación recibida"
    COUNT_PERFORMED = "count_performed", "Arqueo realizado"
    SESSION_CLOSED = "session_closed", "Sesión cerrada"
    DIFFERENCE_DETECTED = "difference_detected", "Diferencia detectada"
