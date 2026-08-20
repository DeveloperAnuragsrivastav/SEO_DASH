from __future__ import annotations
import os
from unittest.mock import patch

import pytest

from app.config import settings
from app.services.google_auth import get_google_credentials


def test_get_google_credentials_missing_env_vars():
    """Test that missing credentials raises ValueError."""
    with patch.object(settings, "google_service_account_json", None):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Google Service Account credentials not found"):
                get_google_credentials()


def test_get_google_credentials_invalid_json():
    """Test that invalid JSON string raises ValueError."""
    with patch.object(settings, "google_service_account_json", "invalid-json"):
        with pytest.raises(ValueError, match="Failed to parse GOOGLE_SERVICE_ACCOUNT_JSON"):
            get_google_credentials()


@patch("app.services.google_auth.service_account.Credentials")
def test_get_google_credentials_valid_raw_json(mock_creds):
    """Test that valid raw JSON loads correctly."""
    mock_creds.from_service_account_info.return_value = "mock_credentials"
    valid_json = '{"project_id": "test"}'

    with patch.object(settings, "google_service_account_json", valid_json):
        creds = get_google_credentials()
        assert creds == "mock_credentials"
        mock_creds.from_service_account_info.assert_called_once()
