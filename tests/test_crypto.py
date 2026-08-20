from __future__ import annotations
import pytest
from app.services.crypto import encrypt_credentials, decrypt_credentials, get_master_key
from app.config import settings

def test_envelope_encryption_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ensure master key is set
    monkeypatch.setattr(settings, "DATAFORSEO_MASTER_KEY", "u-6w7xH7N1A8bL7_Ym0QpD9h9A9bL7_Ym0QpD9h9A9s=")
    
    payload = {"login": "test_user", "password": "super_secret_password"}
    
    # Encrypt
    encrypted_blob = encrypt_credentials(payload)
    
    assert "encrypted_data" in encrypted_blob
    assert "encrypted_dek" in encrypted_blob
    
    # Ensure no plaintext is in the encrypted data
    assert "test_user" not in encrypted_blob["encrypted_data"]
    assert "super_secret_password" not in encrypted_blob["encrypted_data"]
    
    # Decrypt
    decrypted_payload = decrypt_credentials(encrypted_blob)
    
    assert decrypted_payload == payload

def test_missing_master_key_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DATAFORSEO_MASTER_KEY", "")
    with pytest.raises(ValueError, match="DATAFORSEO_MASTER_KEY environment variable is not set"):
        get_master_key()

def test_invalid_blob_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DATAFORSEO_MASTER_KEY", "u-6w7xH7N1A8bL7_Ym0QpD9h9A9bL7_Ym0QpD9h9A9s=")
    
    with pytest.raises(ValueError, match="Invalid encrypted blob format"):
        decrypt_credentials({"foo": "bar"})

def test_invalid_decryption_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DATAFORSEO_MASTER_KEY", "u-6w7xH7N1A8bL7_Ym0QpD9h9A9bL7_Ym0QpD9h9A9s=")
    
    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt_credentials({"encrypted_data": "invalid", "encrypted_dek": "invalid"})
