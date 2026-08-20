from __future__ import annotations
import uuid
import datetime
from sqlalchemy import select
from app.database import SessionLocal
from app.models.account import Account
from app.models.client import Client
from app.models.connection import Connection
from app.models.enums import AccessMode, ClientStatus, ConnectionStatus, ProviderType, SyncStatus, TaskStatus
from app.models.provider_task import ProviderTask
from app.models.sync_run import SyncRun
from app.tasks.rankings import reconcile_sync_runs

def main():
    db = SessionLocal()
    
    # Setup Data
    a = Account(name="Debug Account Reconciliation")
    db.add(a)
    db.flush()
    
    c = Client(
        account_id=a.id,
        name="Debug Client Recon",
        domain="recon.com",
        business_type="local",
        status=ClientStatus.active,
        locale="en-US",
        package_keywords=10,
        onboarded_at=datetime.date.today(),
    )
    db.add(c)
    db.flush()
    
    conn = Connection(
        client_id=c.id,
        provider=ProviderType.dataforseo,
        access_mode=AccessMode.platform_shared,
        property_id="test_prop_recon",
        status=ConnectionStatus.connected,
    )
    db.add(conn)
    db.flush()
    
    sync_run = SyncRun(
        client_id=c.id,
        provider="dataforseo_serp",
        started_at=datetime.datetime.now(datetime.UTC),
        status=SyncStatus.partial,
        rows=1,
    )
    db.add(sync_run)
    db.flush()
    
    ptask = ProviderTask(
        connection_id=conn.id,
        task_id="recon_task_1",
        tag="tag_recon",
        status=TaskStatus.completed,
        submitted_at=datetime.datetime.now(datetime.UTC),
        sync_run_id=sync_run.id
    )
    db.add(ptask)
    db.commit()

    print("--- SYNC_RUN BEFORE RECONCILIATION ---")
    print(f"id: {sync_run.id}")
    print(f"status: {sync_run.status}")
    print(f"finished_at: {sync_run.finished_at}")
    print("--------------------------------------\n")
    
    # Run reconciliation
    reconcile_sync_runs()
    
    db.refresh(sync_run)
    print("--- SYNC_RUN AFTER RECONCILIATION ---")
    print(f"id: {sync_run.id}")
    print(f"status: {sync_run.status}")
    print(f"finished_at: {sync_run.finished_at}")
    print("-------------------------------------")

if __name__ == "__main__":
    main()
