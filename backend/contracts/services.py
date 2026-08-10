from decimal import Decimal

from django.db.models import F, Q

from accounts.models import RoleCode
from plans.models import PlanBranchAvailability

from .choices import ContractActivityAction
from .models import ContractActivity, ContractPlanItem, ContractSequence


SELLER_ROLE_CODES = {RoleCode.SELLER, RoleCode.ADMIN, RoleCode.MANAGER}


def allocate_contract_number(organization):
    sequence, _ = ContractSequence.objects.get_or_create(organization=organization)
    ContractSequence.objects.filter(pk=sequence.pk).update(next_value=F("next_value") + 1)
    sequence.refresh_from_db(fields=("next_value",))
    return f"CTR-{sequence.next_value - 1:06d}"


def plan_is_available(plan, branch):
    if not plan.is_active or plan.organization_id != branch.organization_id:
        return False
    return plan.available_all_branches or PlanBranchAvailability.objects.filter(plan=plan, branch=branch).exists()


def record_contract_activity(contract, user, action, description):
    return ContractActivity.objects.create(
        contract=contract,
        user=user if user and user.is_authenticated else None,
        action=action,
        description=description,
    )


def snapshot_contract(contract):
    customer = contract.customer
    beneficiary = contract.beneficiary
    plan = contract.plan
    contract.plan_name_snapshot = plan.name
    contract.plan_description_snapshot = plan.description
    contract.customer_name_snapshot = customer.full_name
    contract.customer_identity_snapshot = customer.identity_number or ""
    contract.customer_address_snapshot = customer.address
    contract.customer_phone_snapshot = customer.phone
    if not beneficiary or beneficiary.is_customer:
        contract.beneficiary_name_snapshot = customer.full_name
        contract.beneficiary_identity_snapshot = customer.identity_number or ""
        contract.beneficiary_relationship_snapshot = "Titular"
    else:
        contract.beneficiary_name_snapshot = beneficiary.full_name
        contract.beneficiary_identity_snapshot = beneficiary.identity_number or ""
        contract.beneficiary_relationship_snapshot = beneficiary.get_relationship_display()

    contract.plan_items.all().delete()
    ContractPlanItem.objects.bulk_create([
        ContractPlanItem(
            contract=contract,
            original_plan_item=item,
            service=item.service,
            service_code_snapshot=item.service.code,
            service_name_snapshot=item.service.name,
            service_description_snapshot=item.service.description,
            category_snapshot=item.service.get_category_display(),
            quantity=item.quantity,
            unit_snapshot=item.service.get_unit_display(),
            notes_snapshot=item.notes,
            estimated_cost_snapshot=item.service.estimated_cost,
            sort_order=item.sort_order,
        )
        for item in plan.items.select_related("service").filter(included=True).order_by("sort_order", "id")
    ])


def calculate_contract_amounts(subtotal, discount, allow_financing, initial_payment):
    subtotal = Decimal(subtotal)
    discount = Decimal(discount)
    initial_payment = Decimal(initial_payment)
    total = subtotal - discount
    financed = total - initial_payment if allow_financing else Decimal("0.00")
    return total, financed
