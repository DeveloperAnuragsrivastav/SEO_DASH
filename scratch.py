from __future__ import annotations
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
import json

def get_tz():
    creds_path = "google_credentials.json"
    if not os.path.exists(creds_path):
        print("No creds")
        return
    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/analytics.readonly"]
    )
    admin = build("analyticsadmin", "v1beta", credentials=creds)
    # The property_id for GA4 properties is formatted as properties/1234567
    # But usually clients only provide the numeric ID "1234567". We have to pass "properties/1234567"
    # Let's see if we can get a property. I don't have a specific property ID to test on, so I'll just look at the API schema via `dir(admin.properties())`
    print(dir(admin.properties()))

get_tz()
