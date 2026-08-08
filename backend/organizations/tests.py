from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Branch, Organization


class OrganizationBranchTests(TestCase):
    def test_branch_belongs_to_organization(self):
        organization = Organization.objects.create(name="Memora Pruebas", tax_id="TEST-001")
        branch = Branch.objects.create(organization=organization, name="Central", code="CENTRAL")

        self.assertEqual(branch.organization, organization)
        self.assertEqual(list(organization.branches.all()), [branch])

    def test_branch_code_is_unique_inside_organization(self):
        organization = Organization.objects.create(name="Memora Pruebas")
        Branch.objects.create(organization=organization, name="Central", code="CENTRAL")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Branch.objects.create(organization=organization, name="Duplicada", code="CENTRAL")

    def test_active_branch_rejects_inactive_organization_on_validation(self):
        organization = Organization.objects.create(name="Inactiva", is_active=False)
        branch = Branch(organization=organization, name="Central", code="CENTRAL")

        with self.assertRaises(ValidationError):
            branch.full_clean()

