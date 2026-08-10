from django.db import transaction
from django.db.models import F

from .choices import ActivityAction
from .models import CustomerActivity, CustomerSequence


def allocate_customer_code(organization):
    sequence, _ = CustomerSequence.objects.get_or_create(organization=organization)
    CustomerSequence.objects.filter(pk=sequence.pk).update(next_value=F("next_value") + 1)
    sequence.refresh_from_db(fields=("next_value",))
    return f"CLI-{sequence.next_value - 1:06d}"


def add_customer_activity(customer, user, action, description):
    return CustomerActivity.objects.create(
        customer=customer,
        user=user if user and user.is_authenticated else None,
        action=action,
        description=description,
    )


def switch_primary_contact(customer, contact=None):
    queryset = customer.contacts.filter(is_primary=True, is_active=True)
    if contact and contact.pk:
        queryset = queryset.exclude(pk=contact.pk)
    queryset.update(is_primary=False)


ACTIVITY_DESCRIPTIONS = {
    ActivityAction.CREATED: "Se registró el cliente.",
    ActivityAction.UPDATED: "Se actualizó la información del cliente.",
    ActivityAction.ACTIVATED: "Se reactivó el cliente.",
    ActivityAction.DEACTIVATED: "Se inactivó el cliente.",
    ActivityAction.BENEFICIARY_ADDED: "Se agregó un beneficiario.",
    ActivityAction.BENEFICIARY_UPDATED: "Se actualizó un beneficiario.",
    ActivityAction.BENEFICIARY_ACTIVATED: "Se reactivó un beneficiario.",
    ActivityAction.BENEFICIARY_DEACTIVATED: "Se inactivó un beneficiario.",
    ActivityAction.CONTACT_ADDED: "Se agregó un contacto de referencia.",
    ActivityAction.CONTACT_UPDATED: "Se actualizó un contacto de referencia.",
    ActivityAction.CONTACT_ACTIVATED: "Se reactivó un contacto de referencia.",
    ActivityAction.CONTACT_DEACTIVATED: "Se inactivó un contacto de referencia.",
}


def record_activity(customer, user, action):
    return add_customer_activity(customer, user, action, ACTIVITY_DESCRIPTIONS[action])
