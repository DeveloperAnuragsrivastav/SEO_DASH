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

    # Fallback to a key file on disk.
    tried: list[str] = []
    for candidate in _candidate_paths(settings.GOOGLE_APPLICATION_CREDENTIALS):
        tried.append(candidate)
        if os.path.exists(candidate):
            return service_account.Credentials.from_service_account_file(
                candidate, scopes=SCOPES
            )  # type: ignore

    # Name what was actually looked for. Without this the message is the same
    # whether nothing is configured or the path is simply pointing somewhere
    # the process cannot see, which are very different problems.
    where = ", ".join(tried) if tried else "nothing configured"
    raise ValueError(
        "Google Service Account credentials not found. "
        "Set GOOGLE_SERVICE_ACCOUNT_JSON, or point GOOGLE_APPLICATION_CREDENTIALS "
        f"at a readable key file. Looked in: {where}."
    )


def _candidate_paths(configured: str | None) -> list[str]:
    """Where a key file might be, in order of preference.

    The configured path is usually the container's — `/app/...` — because that
    is where the Dockerfile copies the project. Running the same .env locally
    then points at a directory that does not exist. Rather than make one
    deployment's config wrong for the other, fall back to the same filename
    beside the application itself.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    paths: list[str] = []

    if configured:
        paths.append(configured)
        local_twin = os.path.join(project_root, os.path.basename(configured))
        if local_twin not in paths:
            paths.append(local_twin)
    else:
        paths.append(os.path.join(project_root, "google_credentials.json"))

    return paths
