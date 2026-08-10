from django.db.models import F

from .choices import PlanActivityAction
from .models import PlanActivity, PlanSequence


def allocate_plan_code(organization):
    sequence, _ = PlanSequence.objects.get_or_create(organization=organization)
    PlanSequence.objects.filter(pk=sequence.pk).update(next_value=F("next_value") + 1)
    sequence.refresh_from_db(fields=("next_value",))
    return f"PLA-{sequence.next_value - 1:06d}"


ACTIVITY_DESCRIPTIONS = {
    PlanActivityAction.CREATED: "Se creó el plan.",
    PlanActivityAction.UPDATED: "Se actualizó la configuración del plan.",
    PlanActivityAction.SERVICE_ADDED: "Se agregó una prestación al plan.",
    PlanActivityAction.SERVICE_REMOVED: "Se retiró una prestación del plan.",
    PlanActivityAction.ACTIVATED: "Se reactivó el plan.",
    PlanActivityAction.DEACTIVATED: "Se inactivó el plan.",
    PlanActivityAction.DUPLICATED: "El plan se creó como duplicado de otro plan.",
}


def record_plan_activity(plan, user, action, description=None, old_value=None, new_value=None):
    return PlanActivity.objects.create(
        plan=plan,
        user=user if user and user.is_authenticated else None,
        action=action,
        description=description or ACTIVITY_DESCRIPTIONS[action],
        old_value=old_value,
        new_value=new_value,
    )
