import pytest
import httpx
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from app.models.client import Client
from app.models.account import Account
from app.models.link import Link
from app.models.enums import LinkStatus, ClientStatus, BusinessType
from app.services.links import check_client_links_liveness, _check_url_liveness

@pytest.fixture
def setup_test_client(db_session: Session):
    account = Account(name="Test Account")
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    client = Client(
        account_id=account.id,
        name="Link Test Client",
        domain="linktest.com",
        business_type=BusinessType.saas,
        locale="en-US",
        package_keywords=10,
        status=ClientStatus.active,
        onboarded_at=datetime.now(timezone.utc).date()
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    
    # 1. Live link
    link_live = Link(
        client_id=client.id,
        created_on=datetime.now(timezone.utc).date(),
        activity_type="Guest Post",
        domain="live.com",
        url="https://live.com/post",
        status=LinkStatus.active
    )
    
    # 2. Dead link
    link_dead = Link(
        client_id=client.id,
        created_on=datetime.now(timezone.utc).date(),
        activity_type="Directory",
        domain="dead.com",
        url="https://dead.com/link",
        status=LinkStatus.active
    )
    
    # 3. Transient-then-recovered link
    link_transient = Link(
        client_id=client.id,
        created_on=datetime.now(timezone.utc).date(),
        activity_type="Forum",
        domain="transient.com",
        url="https://transient.com/post",
        status=LinkStatus.active
    )
    
    db_session.add_all([link_live, link_dead, link_transient])
    db_session.commit()
    return client.id, link_live.id, link_dead.id, link_transient.id

def test_link_liveness_scenarios(db_session: Session, setup_test_client):
    client_id, live_id, dead_id, transient_id = setup_test_client
    
    # Mock httpx.Client to return specific responses based on URL
    original_head = httpx.Client.head
    original_get = httpx.Client.get
    
    call_counts = {"transient.com": 0}
    
    def mock_head(self, url, *args, **kwargs):
        mock_response = MagicMock()
        if "live.com" in url:
            mock_response.status_code = 200
            return mock_response
        elif "dead.com" in url:
            mock_response.status_code = 404
            return mock_response
        elif "transient.com" in url:
            call_counts["transient.com"] += 1
            if call_counts["transient.com"] < 3:
                raise httpx.TimeoutException("Timeout")
            # Recovers on 3rd attempt
            mock_response.status_code = 200
            return mock_response
        return mock_response

    with patch.object(httpx.Client, 'head', autospec=True, side_effect=mock_head):
        # We need to temporarily disable the retry decorator's wait time for tests so they run fast
        with patch('app.services.links.wait_exponential', return_value=MagicMock(return_value=0.01)):
            check_client_links_liveness(db_session, client_id)

    db_session.expire_all() # Ensure we get fresh data
    
    live_link = db_session.get(Link, live_id)
    dead_link = db_session.get(Link, dead_id)
    transient_link = db_session.get(Link, transient_id)
    
    # 1. Live link should stay active and update last_checked
    assert live_link.status == LinkStatus.active
    assert live_link.last_checked is not None
    
    # 2. Dead link should flip to removed
    assert dead_link.status == LinkStatus.removed
    assert dead_link.last_checked is not None
    
    # 3. Transient link should recover and stay active
    assert transient_link.status == LinkStatus.active
    assert transient_link.last_checked is not None
    assert call_counts["transient.com"] == 3 # Attempted 3 times
