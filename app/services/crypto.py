from __future__ import annotations
import json
from cryptography.fernet import Fernet
from app.config import settings

def get_master_key() -> bytes:
    """Retrieve the master KEK from configuration."""
    key = settings.DATAFORSEO_MASTER_KEY
    if not key:
        raise ValueError("DATAFORSEO_MASTER_KEY environment variable is not set")
    return key.encode()

def encrypt_credentials(payload: dict) -> dict:
    """
    Encrypts a JSON payload using envelope encryption.
    Generates a DEK, encrypts the payload with the DEK,
    and encrypts the DEK with the Master Key.
    """
    master_key = get_master_key()
    master_fernet = Fernet(master_key)

    dek = Fernet.generate_key()
    dek_fernet = Fernet(dek)

    payload_json = json.dumps(payload).encode()
    encrypted_data = dek_fernet.encrypt(payload_json).decode()
    encrypted_dek = master_fernet.encrypt(dek).decode()

    return {
        "encrypted_data": encrypted_data,
        "encrypted_dek": encrypted_dek
    }

def decrypt_credentials(encrypted_blob: dict) -> dict:
    """
    Decrypts a JSON payload using envelope encryption.
    """
    if "encrypted_data" not in encrypted_blob or "encrypted_dek" not in encrypted_blob:
        raise ValueError("Invalid encrypted blob format")

    master_key = get_master_key()
    master_fernet = Fernet(master_key)

    encrypted_dek = encrypted_blob["encrypted_dek"].encode()
    encrypted_data = encrypted_blob["encrypted_data"].encode()

    try:
        dek = master_fernet.decrypt(encrypted_dek)
        dek_fernet = Fernet(dek)
        payload_json = dek_fernet.decrypt(encrypted_data)
        return json.loads(payload_json)
    except Exception as e:
        raise ValueError(f"Decryption failed: {e}")
