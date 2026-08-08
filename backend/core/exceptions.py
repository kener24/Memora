import logging

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


logger = logging.getLogger(__name__)


def _message_for_status(status_code: int) -> str:
    messages = {
        400: "La solicitud contiene datos inválidos.",
        401: "No fue posible autenticar la solicitud.",
        403: "No tiene permisos para realizar esta acción.",
        404: "El recurso solicitado no existe.",
        405: "El método solicitado no está permitido.",
        429: "Se realizaron demasiadas solicitudes.",
    }
    return messages.get(status_code, "No fue posible procesar la solicitud.")


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        logger.exception("Unhandled API exception", exc_info=exc)
        errors = {"detail": [str(exc)]} if settings.DEBUG else {}
        return Response(
            {
                "success": False,
                "message": "Ocurrió un error interno.",
                "errors": errors,
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    detail = response.data
    if isinstance(detail, dict) and set(detail.keys()) == {"detail"}:
        message = str(detail["detail"])
        errors = {}
    else:
        message = _message_for_status(response.status_code)
        errors = detail

    response.data = {
        "success": False,
        "message": message,
        "errors": errors,
    }
    return response

