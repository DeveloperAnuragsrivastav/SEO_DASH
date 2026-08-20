from __future__ import annotations
import uuid
import datetime
from sqlalchemy import select
from app.database import SessionLocal
from app.models.account import Account
from app.models.client import Client
from app.models.connection import Connection
from app.models.keyword import Keyword
from app.models.provider_task import ProviderTask
from app.models.ranking import Ranking
from app.models.enums import AccessMode, ClientStatus, ConnectionStatus, ProviderType, TaskStatus
from app.tasks.rankings import _process_connection

def main():
    db = SessionLocal()
    
    # 1. Setup Data
    a = Account(name="Debug Account")
    db.add(a)
    db.flush()
    
    c = Client(
        account_id=a.id,
        name="Debug Client",
        domain="debug.com",
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
        property_id="test_prop",
        status=ConnectionStatus.connected,
    )
    db.add(conn)
    db.flush()
    
    kw = Keyword(client_id=c.id, term="debug kw", added_at=datetime.date.today())
    db.add(kw)
    db.commit()
    
    # 2. Trigger task post (mock the actual HTTP call)
    from unittest.mock import patch
    with patch("app.tasks.rankings.get_dataforseo_credentials", return_value=("l", "p")):
        with patch("app.tasks.rankings._post_serp_tasks_with_retry", return_value=[{"id": "task_dbg_1", "data": {"tag": f"{c.id}:{kw.id}:{datetime.date.today().isoformat()}"}}]):
            _process_connection(db, conn)
            
    # 3. Query provider_tasks BEFORE webhook
    ptask = db.execute(select(ProviderTask).where(ProviderTask.task_id == "task_dbg_1")).scalar_one()
    print("--- PROVIDER_TASKS ROW BEFORE WEBHOOK ---")
    print(f"id: {ptask.id}")
    print(f"connection_id: {ptask.connection_id}")
    print(f"task_id: {ptask.task_id}")
    print(f"tag: {ptask.tag}")
    print(f"status: {ptask.status}")
    print(f"submitted_at: {ptask.submitted_at}")
    print(f"completed_at: {ptask.completed_at}")
    print(f"cost: {ptask.cost}")
    print("-----------------------------------------\n")
    
    # 4. Simulate Webhook execution
    tag = ptask.tag
    from app.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    
    # We pass 'ai_overview'
    payload = {
        "tasks": [
            {
                "id": "task_dbg_1",
                "data": {"tag": tag},
                "result": [
                    {
                        "items": [
                            {"type": "organic", "rank_group": 3, "url": "https://debug.com"},
                            {"type": "ai_overview"},
                        ]
                    }
                ],
                "cost": 0.0015,
            }
        ]
    }
    
    response = client.post("/api/webhooks/dataforseo/serp", json=payload)
    assert response.status_code == 200
    
    # 5. Query rankings row AFTER webhook
    ranking = db.execute(select(Ranking).where(Ranking.keyword_id == kw.id)).scalar_one()
    print("--- RANKINGS ROW AFTER WEBHOOK (WITH AI OVERVIEW) ---")
    print(f"keyword_id: {ranking.keyword_id}")
    print(f"captured_on: {ranking.captured_on}")
    print(f"position: {ranking.position}")
    print(f"url: {ranking.url}")
    print(f"ai_overview_present: {ranking.ai_overview_present}")
    print(f"source: {ranking.source}")
    print("-----------------------------------------------------")

if __name__ == "__main__":
    main()
