from rest_framework.exceptions import APIException


class ConflictError(APIException):
    status_code = 409
    default_detail = "La operación entra en conflicto con el estado actual del contrato."
    default_code = "conflict"
