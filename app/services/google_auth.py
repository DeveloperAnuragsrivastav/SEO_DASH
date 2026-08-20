from __future__ import annotations
"""Google Service Account credentials loader."""

import base64
import json
import os

from google.oauth2 import service_account

from app.config import settings

# The scopes required for GSC, GA4, and GBP API verification and data pulls
SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/business.manage",
]


def get_google_credentials() -> service_account.Credentials:
    """Load Google Service Account credentials.

    1. Tries to load from GOOGLE_SERVICE_ACCOUNT_JSON (can be raw JSON or base64 encoded).
    2. Falls back to standard GOOGLE_APPLICATION_CREDENTIALS path.
    3. Fails clearly if neither exists.
    """
    json_str = settings.google_service_account_json
    if json_str:
        # Check if it's base64 encoded by trying to decode it
        try:
            # If it's valid JSON directly, this might fail or succeed, but JSON usually starts with '{'
            if json_str.strip().startswith("{"):
                info = json.loads(json_str)
            else:
                decoded = base64.b64decode(json_str).decode("utf-8")
                info = json.loads(decoded)

            return service_account.Credentials.from_service_account_info(
                info, scopes=SCOPES
            )  # type: ignore
        except Exception as e:
            raise ValueError(f"Failed to parse GOOGLE_SERVICE_ACCOUNT_JSON: {e}") from e

    # Fallback to file path
    file_path = settings.GOOGLE_APPLICATION_CREDENTIALS
    if file_path and os.path.exists(file_path):
        return service_account.Credentials.from_service_account_file(
            file_path, scopes=SCOPES
        )  # type: ignore

    raise ValueError(
        "Google Service Account credentials not found. "
        "Set GOOGLE_SERVICE_ACCOUNT_JSON or GOOGLE_APPLICATION_CREDENTIALS."
    )
