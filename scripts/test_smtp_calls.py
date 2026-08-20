from __future__ import annotations
import os
import smtplib
from unittest.mock import patch, MagicMock
from app.utils.alerting import send_email_alert
from app.tasks.rankings import alert_agency
from app.database import SessionLocal
from app.models.connection import Connection
from app.models.client import Client
from app.models.account import Account
from app.models.enums import ConnectionStatus, ProviderType, ClientStatus, BusinessType, AccessMode
from datetime import datetime, UTC

def run_smtp_check():
    os.environ["SMTP_HOST"] = "smtp.mock.local"
    os.environ["ALERT_EMAIL_TO"] = "test@example.com"
    os.environ["ALERT_EMAIL_FROM"] = "alerts@ezrankings.com"

    # Setup dummy data for alert_agency
    with SessionLocal() as db_session:
        account = Account(name="SMTP Check Account")
        db_session.add(account)
        db_session.commit()
        db_session.refresh(account)

        client = Client(
            account_id=account.id,
            name="SMTP Check Client",
            domain="smtpcheck.com",
            business_type=BusinessType.saas,
            locale="en-US",
            package_keywords=10,
            status=ClientStatus.active,
            onboarded_at=datetime.now(UTC).date()
        )
        db_session.add(client)
        db_session.commit()
        db_session.refresh(client)

        conn = Connection(
            client_id=client.id,
            provider=ProviderType.dataforseo,
            access_mode=AccessMode.platform_shared,
            status=ConnectionStatus.connected,
            credentials={"some": "creds"},
            property_id="test_prop",
            property_tz="UTC"
        )
        db_session.add(conn)
        db_session.commit()
        db_session.refresh(conn)
        conn_id = conn.id

    with patch('smtplib.SMTP') as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        
        # 1. Phase 7 call-site
        print("Triggering Phase 7 Alert (Staleness)...")
        alert_agency(conn_id, "DataForSEO task stale_task_123 stalled and timed out after 120 minutes.")
        
        # 2. Phase 10 call-site
        print("\nTriggering Phase 10 Alert (Cost Breach)...")
        send_email_alert(
            subject="[Alert] High API Cost detected",
            message="Daily cost $10.0 exceeds threshold $5.0"
        )
        
        print("\n=== SMTP Send Mock Calls ===")
        for call in mock_server.send_message.call_args_list:
            args, kwargs = call
            msg = args[0]
            print(f"Subject: {msg['Subject']}")
            print(f"From: {msg['From']}")
            print(f"To: {msg['To']}")
            print(f"Content: {msg.get_payload()}")
            print("-" * 20)

if __name__ == "__main__":
    run_smtp_check()
