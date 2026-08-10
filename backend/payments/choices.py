from django.db import models


class PaymentType(models.TextChoices):
    INITIAL_PAYMENT = "initial_payment", "Prima"
    INSTALLMENT = "installment", "Cuota/abono"
    ADVANCE = "advance", "Adelanto"
    SETTLEMENT = "settlement", "Liquidación"
    OTHER = "other", "Otro"


class PaymentMethod(models.TextChoices):
    CASH = "cash", "Efectivo"
    TRANSFER = "transfer", "Transferencia"
    CARD = "card", "Tarjeta"
    CHECK = "check", "Cheque"
    OTHER = "other", "Otro"


class PaymentStatus(models.TextChoices):
    CONFIRMED = "confirmed", "Confirmado"
    VOIDED = "voided", "Anulado"


class ReceiptStatus(models.TextChoices):
    ISSUED = "issued", "Emitido"
    VOIDED = "voided", "Anulado"


class FinancialStatus(models.TextChoices):
    UNPAID = "unpaid", "Sin pagos"
    PARTIAL = "partial", "Pago parcial"
    PAID = "paid", "Pagado"
