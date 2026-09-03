import datetime
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client
from app.models.connection import Connection
from app.models.enums import AccessMode, ClientStatus, ConnectionStatus, ProviderType, RankingSource, TaskStatus
from app.models.keyword import Keyword
from app.models.provider_task import ProviderTask
from app.models.ranking import Ranking
from app.tasks.rankings import trigger_nightly_rankings_pull

client = TestClient(app)


def test_tag_construction_and_webhook_parsing(db_session):
    """Test webhook parsing logic effectively matches task_post logic."""
    client_id = uuid.uuid4()
    keyword_id = uuid.uuid4()
    captured_on = datetime.date(2025, 1, 15)

    from app.models.account import Account
    from app.models.client import Client
    from app.models.connection import Connection
    from app.models.enums import AccessMode, ClientStatus, ConnectionStatus, ProviderType
    
    a = Account(name="Test Account")
    db_session.add(a)
    db_session.flush()

    c = Client(
        account_id=a.id,
        name="Test",
        domain="x.com",
        business_type="local",
        status=ClientStatus.active,
        locale="en-US",
        package_keywords=10,
        onboarded_at=datetime.date.today(),
    )
    db_session.add(c)
    db_session.flush()

    conn = Connection(
        client_id=c.id,
        provider=ProviderType.dataforseo,
        access_mode=AccessMode.platform_shared,
        property_id="test",
        status=ConnectionStatus.connected,
    )
    db_session.add(conn)
    db_session.flush()

    from app.models.keyword import Keyword
    kw = Keyword(client_id=c.id, term="test kw", added_at=datetime.date.today())
    db_session.add(kw)
    db_session.commit()
    keyword_id = kw.id

    # Simulate tag construction
    tag = f"{c.id}:{keyword_id}:{captured_on.isoformat()}"

    # Setup pending task
    ptask = ProviderTask(
        connection_id=conn.id,
        task_id="task123",
        tag=tag,
        status=TaskStatus.pending,
        submitted_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(ptask)
    db_session.commit()

    # Simulate webhook
    payload = {
        "tasks": [
            {
                "id": "task123",
                "data": {"tag": tag},
                "result": [
                    {
                        "items": [
                            {"type": "organic", "rank_group": 5, "url": "https://example.com"},
                            {"type": "ai_overview"},
                        ]
                    }
                ],
                "cost": 0.001,
            }
        ]
    }

    response = client.post("/api/webhooks/dataforseo/serp", json=payload)
    assert response.status_code == 200

    # Verify task updated
    db_session.refresh(ptask)
    assert ptask.status == TaskStatus.completed
    assert float(ptask.cost) == 0.001

    # Verify ranking upserted
    ranking = db_session.query(Ranking).filter_by(keyword_id=keyword_id).first()
    assert ranking is not None
    assert ranking.position == 5
    assert ranking.url == "https://example.com"
    assert ranking.ai_overview_present is True
    assert ranking.source == RankingSource.api


def test_webhook_contract_invalid_tag_rejection(db_session):
    """Test webhook rejects payload with invalid or unmatched tag."""
    # Simulate webhook with unmatched tag/task
    payload = {
        "tasks": [
            {
                "id": "invalid_task",
                "data": {"tag": "fake:tag:123"},
                "result": [{"items": [{"type": "organic", "rank_group": 1, "url": "x.com"}]}],
            }
        ]
    }

    # API should return 200 to acknowledge, but skip processing
    # Because DataForSEO might retry endlessly if we return 400 for a task we genuinely didn't spawn (or spawned in another env)
    # Our webhook logs a warning and continues.
    response = client.post("/api/webhooks/dataforseo/serp", json=payload)
    assert response.status_code == 200

    # Verify no rankings created
    assert db_session.query(Ranking).count() == 0


@patch("app.tasks.rankings.SessionLocal")
@patch("app.tasks.rankings._post_serp_tasks_with_retry")
@patch("app.tasks.rankings.get_dataforseo_credentials")
def test_task_post_batching(mock_get_creds, mock_post, mock_session_local, db_session):
    """Test batching limit (>100 keywords)."""
    mock_session_local.return_value.__enter__.return_value = db_session
    mock_get_creds.return_value = ("test", "test")
    
    # Mock post to return dummy task responses matching payload size
    def side_effect(login, password, payload):
        return [{"id": f"task_{i}", "data": {"tag": p["tag"]}} for i, p in enumerate(payload)]
    
    mock_post.side_effect = side_effect

    from app.models.account import Account
    a = Account(name="Test Account")
    db_session.add(a)
    db_session.flush()

    c = Client(
        account_id=a.id,
        name="Test",
        domain="x.com",
        business_type="local",
        status=ClientStatus.active,
        locale="en-US",
        package_keywords=10,
        onboarded_at=datetime.date.today(),
    )
    db_session.add(c)
    db_session.flush()

    conn = Connection(
        client_id=c.id,
        provider=ProviderType.dataforseo,
        access_mode=AccessMode.platform_shared,
        property_id="test",
        status=ConnectionStatus.connected,
    )
    db_session.add(conn)
    db_session.flush()

    # Add 250 keywords
    for i in range(250):
        kw = Keyword(client_id=c.id, term=f"kw{i}", added_at=datetime.date.today())
        db_session.add(kw)
    db_session.commit()

    # Execute trigger
    trigger_nightly_rankings_pull()

    # Verify mock_post called 3 times (100, 100, 50)
    assert mock_post.call_count == 3
    
    # Verify 250 ProviderTasks created
    assert db_session.query(ProviderTask).count() == 250


@patch("app.tasks.rankings.SessionLocal")
@patch("app.tasks.rankings._post_serp_tasks_with_retry")
@patch("app.tasks.rankings.get_dataforseo_credentials")
def test_retry_then_fail(mock_get_creds, mock_post, mock_session_local, db_session):
    """Test connection is set to error on ultimate failure."""
    mock_session_local.return_value.__enter__.return_value = db_session
    mock_get_creds.return_value = ("test", "test")
    mock_post.side_effect = Exception("API down")

    from app.models.account import Account
    a = Account(name="Test Account")
    db_session.add(a)
    db_session.flush()

    c = Client(
        account_id=a.id,
        name="Test",
        domain="x.com",
        business_type="local",
        status=ClientStatus.active,
        locale="en-US",
        package_keywords=10,
        onboarded_at=datetime.date.today(),
    )
    db_session.add(c)
    db_session.flush()

    conn = Connection(
        client_id=c.id,
        provider=ProviderType.dataforseo,
        access_mode=AccessMode.platform_shared,
        property_id="test",
        status=ConnectionStatus.connected,
    )
    db_session.add(conn)
    
    kw = Keyword(client_id=c.id, term="kw1", added_at=datetime.date.today())
    db_session.add(kw)
    db_session.commit()

    trigger_nightly_rankings_pull()

    # Connection should be marked as error
    db_session.refresh(conn)
    assert conn.status == ConnectionStatus.error
    assert "API down" in conn.last_error
