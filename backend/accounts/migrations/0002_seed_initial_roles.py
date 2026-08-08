from django.db import migrations


ROLES = (
    ("superadmin", "Superadministrador"),
    ("admin", "Administrador"),
    ("manager", "Gerente"),
    ("seller", "Vendedor"),
    ("collector", "Cobrador"),
    ("cashier", "Cajero"),
    ("inventory", "Inventario"),
    ("accountant", "Contador"),
)


def create_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for code, name in ROLES:
        Role.objects.update_or_create(code=code, defaults={"name": name, "is_active": True})


def remove_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    Role.objects.filter(code__in=[code for code, _ in ROLES], users__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [migrations.RunPython(create_roles, remove_roles)]

