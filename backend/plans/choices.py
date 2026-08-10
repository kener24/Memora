from django.db import models


class ServiceCategory(models.TextChoices):
    CASKET = "casket", "Ataúd"
    PREPARATION = "preparation", "Preparación"
    WAKE = "wake", "Velatorio"
    TRANSPORT = "transport", "Transporte"
    DECORATION = "decoration", "Decoración"
    FURNITURE = "furniture", "Mobiliario"
    CEREMONY = "ceremony", "Ceremonia"
    DOCUMENTATION = "documentation", "Documentación"
    CREMATION = "cremation", "Cremación"
    CEMETERY = "cemetery", "Cementerio"
    OTHER = "other", "Otros"


class ServiceUnit(models.TextChoices):
    SERVICE = "service", "Servicio"
    UNIT = "unit", "Unidad"
    HOUR = "hour", "Hora"
    DAY = "day", "Día"
    KILOMETER = "kilometer", "Kilómetro"
    QUANTITY = "quantity", "Cantidad"


class PlanActivityAction(models.TextChoices):
    CREATED = "created", "Plan creado"
    UPDATED = "updated", "Plan actualizado"
    SERVICE_ADDED = "service_added", "Prestación agregada"
    SERVICE_REMOVED = "service_removed", "Prestación retirada"
    PRICE_CHANGED = "price_changed", "Precio actualizado"
    ACTIVATED = "activated", "Plan reactivado"
    DEACTIVATED = "deactivated", "Plan inactivado"
    DUPLICATED = "duplicated", "Plan duplicado"
