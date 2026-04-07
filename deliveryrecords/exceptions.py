from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

_ERROR_CODE_MAP = {
    status.HTTP_400_BAD_REQUEST: "validation_error",
    status.HTTP_401_UNAUTHORIZED: "authentication_failed",
    status.HTTP_403_FORBIDDEN: "permission_denied",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_503_SERVICE_UNAVAILABLE: "service_unavailable",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "server_error",
}


class ServiceUnavailableError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Dependent service is unavailable."
    default_code = "service_unavailable"


def _extract_message(detail):
    if isinstance(detail, dict):
        if "detail" in detail:
            return str(detail["detail"])
        first_value = next(iter(detail.values()), "Request failed.")
        if isinstance(first_value, list) and first_value:
            return str(first_value[0])
        return str(first_value)
    if isinstance(detail, list) and detail:
        return str(detail[0])
    return str(detail)


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return Response(
            {
                "code": _ERROR_CODE_MAP[status.HTTP_500_INTERNAL_SERVER_ERROR],
                "message": "Unexpected server error.",
                "details": {},
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    details = response.data if isinstance(response.data, dict) else {"detail": response.data}
    response.data = {
        "code": _ERROR_CODE_MAP.get(response.status_code, "request_error"),
        "message": _extract_message(response.data),
        "details": details,
    }
    return response
