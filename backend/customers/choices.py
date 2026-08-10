from django.db import models


class HondurasDepartment(models.TextChoices):
    ATLANTIDA = "atlantida", "Atlántida"
    CHOLUTECA = "choluteca", "Choluteca"
    COLON = "colon", "Colón"
    COMAYAGUA = "comayagua", "Comayagua"
    COPAN = "copan", "Copán"
    CORTES = "cortes", "Cortés"
    EL_PARAISO = "el_paraiso", "El Paraíso"
    FRANCISCO_MORAZAN = "francisco_morazan", "Francisco Morazán"
    GRACIAS_A_DIOS = "gracias_a_dios", "Gracias a Dios"
    INTIBUCA = "intibuca", "Intibucá"
    ISLAS_DE_LA_BAHIA = "islas_de_la_bahia", "Islas de la Bahía"
    LA_PAZ = "la_paz", "La Paz"
    LEMPIRA = "lempira", "Lempira"
    OCOTEPEQUE = "ocotepeque", "Ocotepeque"
    OLANCHO = "olancho", "Olancho"
    SANTA_BARBARA = "santa_barbara", "Santa Bárbara"
    VALLE = "valle", "Valle"
    YORO = "yoro", "Yoro"


class Gender(models.TextChoices):
    FEMALE = "female", "Femenino"
    MALE = "male", "Masculino"
    OTHER = "other", "Otro"
    UNSPECIFIED = "unspecified", "Prefiere no indicar"


class MaritalStatus(models.TextChoices):
    SINGLE = "single", "Soltero/a"
    MARRIED = "married", "Casado/a"
    PARTNER = "partner", "Unión libre"
    DIVORCED = "divorced", "Divorciado/a"
    WIDOWED = "widowed", "Viudo/a"
    OTHER = "other", "Otro"


class Relationship(models.TextChoices):
    SELF = "self", "Titular"
    SPOUSE = "spouse", "Cónyuge"
    FATHER = "father", "Padre"
    MOTHER = "mother", "Madre"
    SON = "son", "Hijo"
    DAUGHTER = "daughter", "Hija"
    SIBLING = "sibling", "Hermano/a"
    GRANDPARENT = "grandparent", "Abuelo/a"
    GRANDCHILD = "grandchild", "Nieto/a"
    RELATIVE = "relative", "Familiar"
    OTHER = "other", "Otro"


class ActivityAction(models.TextChoices):
    CREATED = "created", "Cliente creado"
    UPDATED = "updated", "Cliente actualizado"
    ACTIVATED = "activated", "Cliente activado"
    DEACTIVATED = "deactivated", "Cliente inactivado"
    BENEFICIARY_ADDED = "beneficiary_added", "Beneficiario agregado"
    BENEFICIARY_UPDATED = "beneficiary_updated", "Beneficiario actualizado"
    BENEFICIARY_ACTIVATED = "beneficiary_activated", "Beneficiario activado"
    BENEFICIARY_DEACTIVATED = "beneficiary_deactivated", "Beneficiario inactivado"
    CONTACT_ADDED = "contact_added", "Contacto agregado"
    CONTACT_UPDATED = "contact_updated", "Contacto actualizado"
    CONTACT_ACTIVATED = "contact_activated", "Contacto activado"
    CONTACT_DEACTIVATED = "contact_deactivated", "Contacto inactivado"
