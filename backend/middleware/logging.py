"""
Request/response logging middleware for DigitalBazar.
Logs incoming requests and outgoing responses with timing information,
while respecting user privacy and filtering sensitive data.
"""

import json
import logging
import time
import uuid

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("digitalbazar.requests")

# Headers and body fields that must never be logged
SENSITIVE_HEADERS = frozenset({
    "HTTP_AUTHORIZATION",
    "HTTP_COOKIE",
    "HTTP_X_CSRFTOKEN",
})

SENSITIVE_BODY_FIELDS = frozenset({
    "password",
    "password_confirm",
    "old_password",
    "new_password",
    "token",
    "access",
    "refresh",
    "credit_card",
    "card_number",
    "cvv",
    "stripe_token",
    "secret_key",
})

# Paths that should not have their request bodies logged (e.g. file uploads)
SKIP_BODY_PATHS = (
    "/api/v1/products/",  # file uploads happen here
    "/media/",
)


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware that logs every HTTP request and response with:
    - Request ID (for tracing across services)
    - Method, path, query params
    - Response status code
    - Processing duration in milliseconds
    - Client IP address
    """

    def process_request(self, request):
        """Attach request metadata before view processing."""
        request._request_id = str(uuid.uuid4())[:8]
        request._start_time = time.monotonic()

        # Determine client IP
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.META.get("REMOTE_ADDR", "unknown")
        request._client_ip = client_ip

    def process_response(self, request, response):
        """Log the completed request/response cycle."""
        # Calculate duration
        start_time = getattr(request, "_start_time", None)
        duration_ms = (
            round((time.monotonic() - start_time) * 1000, 2)
            if start_time
            else -1
        )

        request_id = getattr(request, "_request_id", "unknown")
        client_ip = getattr(request, "_client_ip", "unknown")
        method = request.method
        path = request.get_full_path()
        status_code = response.status_code
        user = self._get_user_identifier(request)

        log_data = {
            "request_id": request_id,
            "method": method,
            "path": path,
            "status": status_code,
            "duration_ms": duration_ms,
            "ip": client_ip,
            "user": user,
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
        }

        # Log body for non-GET mutating requests (with sensitive data redacted)
        if method in ("POST", "PUT", "PATCH") and not self._should_skip_body(path):
            body = self._get_sanitized_body(request)
            if body:
                log_data["body"] = body

        # Choose log level based on status code
        if status_code >= 500:
            logger.error("%(method)s %(path)s %(status)s [%(duration_ms)sms]", log_data, extra=log_data)
        elif status_code >= 400:
            logger.warning("%(method)s %(path)s %(status)s [%(duration_ms)sms]", log_data, extra=log_data)
        else:
            logger.info("%(method)s %(path)s %(status)s [%(duration_ms)sms]", log_data, extra=log_data)

        # Attach request ID to response headers for client-side tracing
        response["X-Request-ID"] = request_id
        return response

    def _get_user_identifier(self, request):
        """Return a user identifier for logging, or 'anonymous'."""
        if hasattr(request, "user") and request.user.is_authenticated:
            return str(request.user.id)[:8]
        return "anonymous"

    def _should_skip_body(self, path):
        """Check if the request body should be skipped for logging."""
        return any(
            path.startswith(skip_path) and "files" in path
            for skip_path in SKIP_BODY_PATHS
        )

    def _get_sanitized_body(self, request):
        """
        Extract and sanitize the request body for logging.
        Redacts sensitive fields and truncates large payloads.
        """
        try:
            if request.content_type and "multipart" in request.content_type:
                return {"_note": "multipart/form-data (body omitted)"}

            body = request.body
            if not body:
                return None

            if len(body) > 10_000:
                return {"_note": f"Body too large ({len(body)} bytes), truncated."}

            data = json.loads(body)
            if isinstance(data, dict):
                return {
                    key: "***REDACTED***" if key.lower() in SENSITIVE_BODY_FIELDS else value
                    for key, value in data.items()
                }
            return data

        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
