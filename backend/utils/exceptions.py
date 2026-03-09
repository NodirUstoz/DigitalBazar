"""
Custom exception handler for the DigitalBazar API.
Provides consistent error response format across all endpoints.
"""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that normalizes all error responses to a
    consistent format:
    {
        "error": true,
        "code": "error_code",
        "message": "Human-readable message",
        "details": { ... }  // optional field-level errors
    }
    """
    # Let DRF handle the exception first to get the standard response
    response = exception_handler(exc, context)

    if response is None:
        # Unhandled exception -- log and return 500
        if isinstance(exc, DjangoValidationError):
            data = {
                "error": True,
                "code": "validation_error",
                "message": "Validation failed.",
                "details": exc.message_dict if hasattr(exc, "message_dict") else {"non_field_errors": exc.messages},
            }
            return Response(data, status=status.HTTP_400_BAD_REQUEST)

        logger.exception(
            "Unhandled exception in %s %s",
            context.get("request", {}).method if context.get("request") else "UNKNOWN",
            context.get("request", {}).path if context.get("request") else "UNKNOWN",
        )
        data = {
            "error": True,
            "code": "internal_server_error",
            "message": "An unexpected error occurred. Please try again later.",
        }
        return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Build normalized error body
    error_data = {
        "error": True,
        "code": _get_error_code(exc),
        "message": _get_error_message(exc, response),
    }

    # Attach field-level details for validation errors
    if isinstance(exc, ValidationError) and isinstance(response.data, dict):
        error_data["details"] = response.data

    response.data = error_data
    return response


def _get_error_code(exc):
    """Map exception types to machine-readable error codes."""
    code_map = {
        ValidationError: "validation_error",
        AuthenticationFailed: "authentication_failed",
        NotAuthenticated: "not_authenticated",
        PermissionDenied: "permission_denied",
        Http404: "not_found",
    }
    for exc_class, code in code_map.items():
        if isinstance(exc, exc_class):
            return code

    if hasattr(exc, "default_code"):
        return exc.default_code
    return "error"


def _get_error_message(exc, response):
    """Extract a human-readable message from the exception."""
    if isinstance(exc, ValidationError):
        if isinstance(response.data, list):
            return response.data[0] if response.data else "Validation error."
        if isinstance(response.data, dict):
            # Return first error message from first field
            for field, messages in response.data.items():
                if isinstance(messages, list) and messages:
                    return f"{field}: {messages[0]}"
                if isinstance(messages, str):
                    return f"{field}: {messages}"
        return "Validation error."

    if hasattr(exc, "detail"):
        detail = exc.detail
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list):
            return detail[0] if detail else str(exc)
        if isinstance(detail, dict):
            first_key = next(iter(detail), None)
            if first_key:
                val = detail[first_key]
                if isinstance(val, list):
                    return str(val[0])
                return str(val)

    return str(exc)


class ServiceUnavailable(APIException):
    """Raised when an external service (Stripe, email, etc.) is unreachable."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Service temporarily unavailable. Please try again shortly."
    default_code = "service_unavailable"


class PaymentProcessingError(APIException):
    """Raised when a payment operation fails."""

    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "Payment processing failed."
    default_code = "payment_error"


class DownloadLimitExceeded(APIException):
    """Raised when the user exceeds their download limit."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "Download limit exceeded for this license."
    default_code = "download_limit_exceeded"
