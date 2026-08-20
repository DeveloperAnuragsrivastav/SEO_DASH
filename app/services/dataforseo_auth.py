from __future__ import annotations
import base64
import uuid

import httpx
from sqlalchemy.orm import Session
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.models.connection import AccessMode, Connection
from app.services.crypto import decrypt_credentials


def validate_dataforseo_credentials(login: str, password: str) -> bool:
    """
    Validates DataForSEO credentials by making a lightweight call to the user_data endpoint.
    Returns True if valid. Raises ValueError on authentication failure or other errors.
    """
    url = "https://api.dataforseo.com/v3/appendix/user_data"
    auth_str = f"{login}:{password}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {"Authorization": f"Basic {encoded_auth}"}

    try:
        response = httpx.get(url, headers=headers, timeout=10.0)
    except Exception as e:
        raise ValueError(f"Failed to connect to DataForSEO API: {e}")

    if response.status_code != 200:
        raise ValueError(f"DataForSEO API error: HTTP {response.status_code}")

    try:
        data = response.json()
    except Exception:
        raise ValueError("Invalid JSON response from DataForSEO API")

    status_code = data.get("status_code", 0)
    
    # 20000 indicates success in DataForSEO API
    if status_code != 20000:
        status_message = data.get("status_message", "Unknown error")
        raise ValueError(f"DataForSEO authentication failed: Code {status_code}, Message: {status_message}")

    return True


def get_dataforseo_credentials(db: Session, connection_id: uuid.UUID) -> tuple[str, str]:
    """
    Retrieves the (login, password) for a DataForSEO connection.
    If platform_shared, uses environment variables.
    If client_owned, decrypts the credentials from the database.
    """
    conn = db.get(Connection, connection_id)
    if not conn or conn.provider != "dataforseo":
        raise ValueError("Invalid connection")

    if conn.access_mode == AccessMode.platform_shared:
        login = settings.DATAFORSEO_LOGIN
        password = settings.DATAFORSEO_PASSWORD
        if not login or not password:
            raise ValueError("Platform DataForSEO credentials are not configured")
        return login, password

    if not conn.credentials:
        raise ValueError("No credentials found for client_owned connection")

    try:
        decrypted = decrypt_credentials(conn.credentials)
    except Exception as e:
        raise ValueError(f"Failed to decrypt credentials: {e}")

    login = decrypted.get("login")
    password = decrypted.get("password")

    if not login or not password:
        raise ValueError("Invalid decrypted credentials structure")

    return login, password


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _post_serp_tasks_with_retry(login: str, password: str, payload: list[dict]) -> list[dict]:
    """Posts a batch of SERP tasks to DataForSEO. Retries on ANY exception (network, API) up to 3 times."""
    url = "https://api.dataforseo.com/v3/serp/google/organic/task_post"
    auth_str = f"{login}:{password}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded_auth}",
        "Content-Type": "application/json"
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=30.0)
    except Exception as e:
        raise ValueError(f"Failed to connect to DataForSEO task_post API: {e}")

    if response.status_code != 200:
        raise ValueError(f"DataForSEO task_post API error: HTTP {response.status_code}")

    try:
        data = response.json()
    except Exception:
        raise ValueError("Invalid JSON response from DataForSEO task_post API")

    status_code = data.get("status_code", 0)
    if status_code != 20000:
        status_message = data.get("status_message", "Unknown error")
        raise ValueError(f"DataForSEO task_post failed: Code {status_code}, Message: {status_message}")

    return data.get("tasks", [])
