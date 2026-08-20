from __future__ import annotations
import pytest
from datetime import datetime, timezone.utc, timedelta
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from app.models.client import Client
from app.models.account import Account
from app.models.connection import Connection
from app.models.enums import ConnectionStatus, ProviderType, SyncStatus, TaskStatus, ClientStatus, BusinessType, AccessMode
from app.models.sync_run import SyncRun
from app.models.provider_task import ProviderTask
from app.tasks.rankings import reconcile_sync_runs
from app.tasks.cost_guardrail import aggregate_daily_cost
import smtplib
import os

os.environ["SMTP_HOST"] = "smtp.mock.local"
os.environ["ALERT_EMAIL_TO"] = "test@example.com"

@pytest.fixture
def setup_alert_data(db_session: Session):
    account = Account(name="Alert Test Account")
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    client = Client(
        account_id=account.id,
        name="Alert Test Client",
        domain="alert.com",
        business_type=BusinessType.saas,
        locale="en-US",
        package_keywords=10,
        status=ClientStatus.active,
        onboarded_at=datetime.now(timezone.utc).date()
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
        property_tz="timezone.utc"
    )
    db_session.add(conn)
    db_session.commit()
    db_session.refresh(conn)

    # Phase 7 setup
    staleness_time = datetime.now(timezone.utc) - timedelta(minutes=130) # 130 mins ago
    
    sync_run_stale = SyncRun(
        client_id=client.id,
        provider=ProviderType.dataforseo.value,
        status=SyncStatus.partial,
        started_at=staleness_time
    )
    db_session.add(sync_run_stale)
    db_session.commit()
    db_session.refresh(sync_run_stale)
    
    ptask = ProviderTask(
        sync_run_id=sync_run_stale.id,
        connection_id=conn.id,
        task_id="stale_task_123",
        tag="test_tag",
        status=TaskStatus.pending,
        submitted_at=staleness_time
    )
    db_session.add(ptask)
    
    # Phase 10 setup
    # aggregate_daily_cost queries today's costs. We need today's cost > 5.0
    sync_run_cost = SyncRun(
        client_id=client.id,
        provider="groq",
        status=SyncStatus.success,
        started_at=datetime.now(timezone.utc),
        cost=10.0 # > 5.0
    )
    db_session.add(sync_run_cost)
    db_session.commit()
    
    return client, conn

def test_smtp_mocked_alerts(setup_alert_data, capsys):
    client, conn = setup_alert_data
    
    with patch('smtplib.SMTP') as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        
        # Trigger Phase 7
        reconcile_sync_runs()
        
        # Trigger Phase 10
        aggregate_daily_cost()
        
        # Print out the mocked calls
        print("\n=== SMTP Send Mock Calls ===")
        for call in mock_server.send_message.call_args_list:
            args, kwargs = call
            msg = args[0]
            print(f"Subject: {msg['Subject']}")
            print(f"To: {msg['To']}")
            print(f"Content: {msg.get_payload()}")
            print("-" * 20)
