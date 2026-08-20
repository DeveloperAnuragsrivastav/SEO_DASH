from __future__ import annotations
import sys
import os

# Append the project root to sys.path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
from app.tasks.cost_guardrail import alert_agency as cg_alert_agency
from app.tasks.rankings import alert_agency as r_alert_agency
from app.database import SessionLocal
from app.models.connection import Connection
from app.models.client import Client
import uuid
from datetime import date

def test_alerting():
    print("\n--- Testing Alerting Mechanisms ---\n")
    
    # 1. Test without SMTP configured (fallback)
    print("Test 1: Fallback (No SMTP configured)")
    os.environ.pop("SMTP_HOST", None)
    os.environ.pop("ALERT_EMAIL_TO", None)
    
    cg_alert_agency("Test Subject Fallback", "This should just log securely.")
    print("Fallback test completed. Check logs above.\n")
    
    # 2. Test with SMTP configured
    print("Test 2: Mocked SMTP Server")
    os.environ["SMTP_HOST"] = "smtp.example.com"
    os.environ["SMTP_PORT"] = "587"
    os.environ["SMTP_USER"] = "testuser"
    os.environ["SMTP_PASSWORD"] = "testpass"
    os.environ["ALERT_EMAIL_FROM"] = "alerts@ezrankings.com"
    os.environ["ALERT_EMAIL_TO"] = "agency@ezrankings.com"
    
    with patch("app.utils.alerting.smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        
        # Test Cost Guardrail
        cg_alert_agency("Cost Guardrail Breach", "GSC cost exceeded 3x average.")
        
        # Test Rankings (needs a mock DB connection to grab client name)
        db = SessionLocal()
        try:
            conn = db.query(Connection).first()
            if conn:
                conn_id = conn.id
                r_alert_agency(conn_id, "SERP fetch failed after 3 retries.")
            else:
                print("No connection found in DB, skipping Rankings alert test.")
        finally:
            db.close()
            
        # Verify calls
        assert mock_server.send_message.call_count >= 1
        calls = mock_server.send_message.call_args_list
        
        # Check first call (Cost Guardrail)
        msg1 = calls[0][0][0]
        print(f"Call 1 (Cost Guardrail):")
        print(f"  To: {msg1['To']}")
        print(f"  From: {msg1['From']}")
        print(f"  Subject: {msg1['Subject']}")
        print(f"  Body: {msg1.get_payload()}")
        
        # Check second call (Rankings) if it ran
        if len(calls) > 1:
            msg2 = calls[1][0][0]
            print(f"\nCall 2 (Rankings/Connections):")
            print(f"  To: {msg2['To']}")
            print(f"  From: {msg2['From']}")
            print(f"  Subject: {msg2['Subject']}")
            print(f"  Body: {msg2.get_payload()}")
        
if __name__ == "__main__":
    test_alerting()
