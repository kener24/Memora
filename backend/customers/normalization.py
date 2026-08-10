import re

from django.core.exceptions import ValidationError


SPACE_PATTERN = re.compile(r"\s+")
PHONE_PATTERN = re.compile(r"^[0-9()+-]+$")
IDENTITY_PATTERN = re.compile(r"^[A-Z0-9-]+$")


def normalize_text(value):
    if value is None:
        return ""
    return SPACE_PATTERN.sub(" ", str(value).strip())


def normalize_email(value):
    return normalize_text(value).lower()


def normalize_phone(value):
    compact = re.sub(r"\s+", "", str(value or "").strip())
    if not compact:
        return ""
    if not PHONE_PATTERN.fullmatch(compact):
        raise ValidationError("Utiliza únicamente números, paréntesis, + o guiones.")
    digits = re.sub(r"\D", "", compact)
    if not 8 <= len(digits) <= 15:
        raise ValidationError("El teléfono debe contener entre 8 y 15 dígitos.")
    return compact

def normalize_identity(value):
    compact = re.sub(r"\s+", "", str(value or "").strip()).upper()
    if not compact:
        return None
    if not IDENTITY_PATTERN.fullmatch(compact):
        raise ValidationError("La identidad contiene caracteres no permitidos.")
    plain = compact.replace("-", "")
    if not 5 <= len(plain) <= 25:
        raise ValidationError("La identidad debe contener entre 5 y 25 caracteres.")
    if plain.isdigit() and len(plain) == 13:
        return plain
    return compact
