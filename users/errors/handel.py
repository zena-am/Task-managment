import logging

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import (ValidationError,NotAuthenticated,PermissionDenied)
from users.errors.exceptions import BaseAppException


logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    # =========================
    # Custom Business Exceptions
    # الأخطاء التي أنت عاملها في exceptions.py
    # =========================
    if isinstance(exc, BaseAppException):
        return Response(
            {
                "success": False,
                "code": exc.detail.get("code"),
                "message": exc.detail.get("message"),
                "data": None,
                "errors": None
            },
            status=exc.status_code,
        )
        """ 
    if isinstance(exc, BaseAppException):
        return Response(
            {
                "success": False,
                    "code": (
            exc.detail.get("code")
            if isinstance(exc.detail, dict)
            else getattr(exc, "default_code", "BUSINESS_ERROR")
            ),
            "message": (
                exc.detail.get("message")
                if isinstance(exc.detail, dict)
                else str(exc.detail)
            ),
            "errors": exc.detail.get("errors") if isinstance(exc.detail, dict) else None
            },
            status=exc.status_code,
        )
"""

    # =========================
    # Validation Errors
    # أخطاء serializer مثل required / invalid
    # =========================
    if isinstance(exc, ValidationError):
        return Response(
            {
                "success": False,
                "code": "VALIDATION_ERROR",
                "message": "Validation error",
                "data": None,
                "errors": response.data if response else None,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================
    # Authentication Errors
    # المستخدم غير مسجل دخول
    # =========================
    if isinstance(exc, NotAuthenticated):
        return Response(
            {
                "success": False,
                "code": "NOT_AUTHENTICATED",
                "message": "Authentication required",
                "data": None,
                "errors": None,
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # =========================
    # Permission Errors
    # لا يملك صلاحية
    # =========================
    if isinstance(exc, PermissionDenied):
        return Response(
            {
                "success": False,
                "code": "PERMISSION_DENIED",
                "message": "Permission denied",
                "data": None,
                "errors": None,
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # =========================
    # Other DRF Errors
    # مثل NotFound / MethodNotAllowed
    # =========================
    if response is not None:
        return Response(
            {
                "success": False,
                "code": "ERROR",
                "message": response.data.get("detail", "Something went wrong")
                if isinstance(response.data, dict)
                else "Something went wrong",
                "data": None,
                "errors": None,
            },
            status=response.status_code,
        )

    # =========================
    # Unexpected Server Errors
    # أخطاء غير متوقعة
    # =========================
    logger.exception("Unhandled exception: %s", exc)

    return Response(
        {
            "success": False,
            "code": "SERVER_ERROR",
            "message": "Internal server error",
            "data": None,
            "errors": None,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )