"""
Advanced rate-limiting middleware for DigitalBazar.
Provides endpoint-specific rate limits on top of DRF's built-in throttling,
with special handling for authentication, downloads, and payment endpoints.
"""

import hashlib
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("digitalbazar.ratelimit")

# Rate limit configuration: path_prefix -> (max_requests, window_seconds)
RATE_LIMIT_RULES = {
    "/api/v1/auth/login": (10, 300),          # 10 login attempts per 5 minutes
    "/api/v1/auth/register": (5, 3600),        # 5 registrations per hour
    "/api/v1/auth/password/reset": (3, 3600),  # 3 password resets per hour
    "/api/v1/orders/checkout": (20, 3600),     # 20 checkouts per hour
    "/api/v1/payments/webhook": (100, 60),     # 100 webhook calls per minute
    "/api/v1/orders/licenses/validate": (60, 60),  # 60 validations per minute
}

# Endpoints exempt from rate limiting
EXEMPT_PATHS = (
    "/admin/",
    "/static/",
    "/media/",
    "/health/",
)

# Default global rate limit for authenticated users
DEFAULT_AUTH_RATE = (200, 60)       # 200 requests per minute
# Default global rate limit for anonymous users
DEFAULT_ANON_RATE = (60, 60)        # 60 requests per minute

# Cache key prefix
CACHE_PREFIX = "rl"


class RateLimitMiddleware(MiddlewareMixin):
    """
    Token-bucket-style rate limiting using Django cache (Redis).

    Features:
    - Per-endpoint rate limits for sensitive operations
    - Separate limits for authenticated vs anonymous users
    - Sliding window counter implementation
    - Returns standard 429 response with Retry-After header
    - Logs rate limit violations for monitoring
    """

    def process_request(self, request):
        """Check rate limits before request processing."""
        path = request.path

        # Skip exempt paths
        if any(path.startswith(exempt) for exempt in EXEMPT_PATHS):
            return None

        # Determine the client identity key
        identity = self._get_client_identity(request)

        # Check endpoint-specific rate limits first
        for rule_path, (max_requests, window) in RATE_LIMIT_RULES.items():
            if path.rstrip("/").startswith(rule_path.rstrip("/")):
                blocked = self._check_rate_limit(
                    identity, rule_path, max_requests, window
                )
                if blocked:
                    return self._rate_limit_response(blocked, path, identity)
                return None

        # Apply default global rate limit
        if hasattr(request, "user") and getattr(request.user, "is_authenticated", False):
            max_requests, window = DEFAULT_AUTH_RATE
        else:
            max_requests, window = DEFAULT_ANON_RATE

        blocked = self._check_rate_limit(identity, "global", max_requests, window)
        if blocked:
            return self._rate_limit_response(blocked, path, identity)

        return None

    def _get_client_identity(self, request):
        """
        Build a unique identity string for the client.
        Uses user ID for authenticated requests, IP for anonymous.
        """
        if hasattr(request, "user") and getattr(request.user, "is_authenticated", False):
            raw = f"user:{request.user.id}"
        else:
            x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
            if x_forwarded:
                ip = x_forwarded.split(",")[0].strip()
            else:
                ip = request.META.get("REMOTE_ADDR", "0.0.0.0")
            raw = f"ip:{ip}"

        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def _check_rate_limit(self, identity, scope, max_requests, window):
        """
        Sliding window counter rate limiter using Redis/cache.

        Returns None if allowed, or seconds until the window resets if blocked.
        """
        cache_key = f"{CACHE_PREFIX}:{scope}:{identity}"

        try:
            # Retrieve current window data
            data = cache.get(cache_key)

            now = time.time()

            if data is None:
                # First request in this window
                cache.set(
                    cache_key,
                    {"count": 1, "window_start": now},
                    timeout=window,
                )
                return None

            window_start = data.get("window_start", now)
            elapsed = now - window_start

            if elapsed >= window:
                # Window has expired; start a new one
                cache.set(
                    cache_key,
                    {"count": 1, "window_start": now},
                    timeout=window,
                )
                return None

            count = data.get("count", 0) + 1

            if count > max_requests:
                retry_after = int(window - elapsed) + 1
                return retry_after

            # Update counter
            data["count"] = count
            remaining_ttl = int(window - elapsed) + 1
            cache.set(cache_key, data, timeout=remaining_ttl)
            return None

        except Exception as exc:
            # On cache failure, allow the request through and log
            logger.warning(
                "Rate limit check failed for %s: %s", identity, exc
            )
            return None

    def _rate_limit_response(self, retry_after, path, identity):
        """Return a 429 Too Many Requests response."""
        logger.warning(
            "Rate limit exceeded: identity=%s path=%s retry_after=%ds",
            identity,
            path,
            retry_after,
        )
        response = JsonResponse(
            {
                "error": True,
                "code": "rate_limit_exceeded",
                "message": "Too many requests. Please slow down.",
                "retry_after": retry_after,
            },
            status=429,
        )
        response["Retry-After"] = str(retry_after)
        return response
