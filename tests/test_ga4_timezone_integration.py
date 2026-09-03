import pytest
from app.services.google_clients import verify_ga4
import os

@pytest.mark.skipif(not os.getenv("RUN_LIVE_TESTS"), reason="Needs live GA4 credentials")
def test_live_verify_ga4():
    property_id = "314407318"
    
    assert os.getenv("GOOGLE_APPLICATION_CREDENTIALS") is not None
    
    timezone = verify_ga4(property_id)
    
    assert isinstance(timezone, str)
    assert "/" in timezone
    print(f"\nLIVE GA4 TIMEZONE FETCHED: {timezone}")
