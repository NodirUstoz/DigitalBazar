"""
License key generation utilities for DigitalBazar.
Generates unique, cryptographically secure license keys in various formats.
"""

import hashlib
import secrets
import string
import uuid
from datetime import datetime


def generate_license_key(
    prefix: str = "DB",
    segments: int = 4,
    segment_length: int = 5,
    separator: str = "-",
) -> str:
    """
    Generate a unique, human-readable license key.

    Format: PREFIX-XXXXX-XXXXX-XXXXX-XXXXX
    Uses uppercase alphanumeric characters excluding ambiguous ones (0/O, 1/I/L).

    Args:
        prefix: Key prefix for identification (default: "DB").
        segments: Number of character segments (default: 4).
        segment_length: Characters per segment (default: 5).
        separator: Separator between segments (default: "-").

    Returns:
        A formatted license key string.
    """
    # Characters excluding ambiguous ones for readability
    charset = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

    parts = [prefix]
    for _ in range(segments):
        segment = "".join(secrets.choice(charset) for _ in range(segment_length))
        parts.append(segment)

    return separator.join(parts)


def generate_activation_token() -> str:
    """
    Generate a one-time activation token for software activation flows.
    Returns a 64-character hex string based on system entropy.
    """
    return secrets.token_hex(32)


def generate_download_token(
    license_key_id: str,
    file_id: str,
    user_id: str,
    secret: str = "",
) -> str:
    """
    Generate a signed, time-limited download token.
    Used to create secure download URLs that expire.

    Args:
        license_key_id: The license key UUID.
        file_id: The product file UUID.
        user_id: The requesting user UUID.
        secret: Application secret for HMAC signing.

    Returns:
        A signed token string.
    """
    timestamp = datetime.utcnow().isoformat()
    payload = f"{license_key_id}:{file_id}:{user_id}:{timestamp}"
    signature = hashlib.sha256(
        f"{payload}:{secret}".encode("utf-8")
    ).hexdigest()
    return f"{payload}:{signature}"


def validate_download_token(token: str, secret: str = "", max_age_seconds: int = 86400) -> dict:
    """
    Validate a download token and check expiration.

    Args:
        token: The token to validate.
        secret: Application secret for HMAC verification.
        max_age_seconds: Maximum token age in seconds (default: 24 hours).

    Returns:
        dict with 'valid' boolean and parsed token fields,
        or 'valid': False with an 'error' message.
    """
    try:
        parts = token.rsplit(":", 1)
        if len(parts) != 2:
            return {"valid": False, "error": "Malformed token."}

        payload, provided_signature = parts
        expected_signature = hashlib.sha256(
            f"{payload}:{secret}".encode("utf-8")
        ).hexdigest()

        if not secrets.compare_digest(provided_signature, expected_signature):
            return {"valid": False, "error": "Invalid token signature."}

        segments = payload.split(":")
        if len(segments) != 4:
            return {"valid": False, "error": "Malformed token payload."}

        license_key_id, file_id, user_id, timestamp = segments

        created_at = datetime.fromisoformat(timestamp)
        age = (datetime.utcnow() - created_at).total_seconds()
        if age > max_age_seconds:
            return {"valid": False, "error": "Token has expired."}

        return {
            "valid": True,
            "license_key_id": license_key_id,
            "file_id": file_id,
            "user_id": user_id,
            "created_at": timestamp,
        }

    except (ValueError, TypeError) as exc:
        return {"valid": False, "error": f"Token validation failed: {exc}"}


def generate_short_code(length: int = 8) -> str:
    """
    Generate a short alphanumeric code.
    Suitable for referral codes, coupon codes, etc.
    """
    charset = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(charset) for _ in range(length))
