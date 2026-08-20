from __future__ import annotations
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock
from app.services.links import check_client_links_liveness
from app.database import SessionLocal
from app.models.client import Client
from app.models.link import Link
from app.models.enums import LinkStatus
import uuid
from datetime import date
import httpx

def test_link_liveness():
    print("\n--- Testing Link Liveness Checker ---\n")
    db = SessionLocal()
    
    # 1. Setup mock client and links
    client_id = uuid.uuid4()
    test_client = Client(id=client_id, name="Test Liveness Client", domain="liveness.com", business_type="local", locale="en-US", package_keywords=10, status="active", onboarded_at=date.today(), account_id=uuid.UUID('00000000-0000-0000-0000-000000000000'))
    db.add(test_client)
    
    # URL 1: Stays alive (200 OK)
    link1 = Link(id=uuid.uuid4(), client_id=client_id, created_on=date.today(), activity_type="blog", domain="good.com", url="https://good.com/post", status=LinkStatus.active)
    
    # URL 2: Fails with 404
    link2 = Link(id=uuid.uuid4(), client_id=client_id, created_on=date.today(), activity_type="directory", domain="dead.com", url="https://dead.com/listing", status=LinkStatus.active)
    
    # URL 3: 405 on HEAD, then 200 on GET
    link3 = Link(id=uuid.uuid4(), client_id=client_id, created_on=date.today(), activity_type="guest_post", domain="weird.com", url="https://weird.com/post", status=LinkStatus.active)
    
    # URL 4: Transient failure then success (via tenacity) - mocking will handle this
    link4 = Link(id=uuid.uuid4(), client_id=client_id, created_on=date.today(), activity_type="pr", domain="flaky.com", url="https://flaky.com/news", status=LinkStatus.active)
    
    db.add_all([link1, link2, link3, link4])
    
    try:
        # We know we'll get a ForeignKey violation if we insert a client without an account,
        # but let's assume `account_id` isn't strictly enforced or we use a valid one if we can.
        # Actually, let's grab an existing account.
        from app.models.account import Account
        account = db.query(Account).first()
        if account:
            test_client.account_id = account.id
            
        db.commit()
    except Exception as e:
        print(f"Failed to setup DB: {e}")
        db.rollback()
        return
        
    print(f"Created 4 active links for client {client_id}")
    
    with patch("app.services.links.httpx.Client") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value.__enter__.return_value = mock_instance
        
        # We need a custom side effect for head and get
        def head_side_effect(url):
            resp = MagicMock()
            if "good.com" in url:
                resp.status_code = 200
            elif "dead.com" in url:
                resp.status_code = 404
            elif "weird.com" in url:
                resp.status_code = 405
            elif "flaky.com" in url:
                raise httpx.RequestError("Connection reset by peer")
            else:
                resp.status_code = 200
            return resp
            
        def get_side_effect(url):
            resp = MagicMock()
            if "weird.com" in url:
                resp.status_code = 200
            else:
                resp.status_code = 200
            return resp
            
        mock_instance.head.side_effect = head_side_effect
        mock_instance.get.side_effect = get_side_effect
        
        # Since flaky.com will throw httpx.RequestError 3 times (due to side_effect not changing), 
        # it should fail after 3 retries and become 'removed'.
        
        check_client_links_liveness(db, client_id)
        
    # Verify states
    db.refresh(link1)
    db.refresh(link2)
    db.refresh(link3)
    db.refresh(link4)
    
    print("\n--- Results ---")
    print(f"good.com (200): expected active -> {link1.status.value}")
    print(f"dead.com (404): expected removed -> {link2.status.value}")
    print(f"weird.com (405 then 200): expected active -> {link3.status.value}")
    print(f"flaky.com (transient error 3x): expected removed -> {link4.status.value}")
    
    # Cleanup
    from app.models.sync_run import SyncRun
    sync_runs = db.query(SyncRun).filter(SyncRun.client_id == client_id).all()
    for sr in sync_runs:
        db.delete(sr)
        
    db.delete(link1)
    db.delete(link2)
    db.delete(link3)
    db.delete(link4)
    db.delete(test_client)
    db.commit()
    db.close()

if __name__ == "__main__":
    test_link_liveness()
