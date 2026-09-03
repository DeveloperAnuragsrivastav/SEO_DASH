import datetime
import uuid
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.account import Account
from app.models.client import Client
from app.models.connection import Connection
from app.models.enums import AccessMode, AiPlatform, AiMentionSource, ClientStatus, ConnectionStatus, ProviderType, SyncStatus
from app.models.ai_prompt import AiPrompt
from app.models.ai_mention import AiMention
from app.models.sync_run import SyncRun
from app.tasks.ai_visibility import _process_ai_visibility, PLATFORMS

client = TestClient(app)

@pytest.fixture
def base_data(db_session):
    a = Account(name="Test Account")
    db_session.add(a)
    db_session.flush()

    c = Client(
        account_id=a.id,
        name="Test",
        domain="example.com",
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
        property_id="test_dfs",
        status=ConnectionStatus.connected,
    )
    db_session.add(conn)
    db_session.commit()

    return {"client": c, "connection": conn}


def test_ai_prompts_crud(base_data, db_session):
    client_id = base_data["client"].id
    
    # Create
    response = client.post(
        f"/clients/{client_id}/ai_prompts",
        json={"prompt_text": "What are the best local SEO tools?"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["prompt_text"] == "What are the best local SEO tools?"
    assert data["is_active"] is True
    prompt_id = data["id"]
    
    # List
    response = client.get(f"/clients/{client_id}/ai_prompts")
    assert response.status_code == 200
    assert len(response.json()) == 1
    
    # Update (Deactivate)
    response = client.put(
        f"/clients/{client_id}/ai_prompts/{prompt_id}",
        json={"is_active": False}
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    
    # List again (should be empty since it only returns active prompts)
    response = client.get(f"/clients/{client_id}/ai_prompts")
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_ai_mentions_manual_fallback(base_data, db_session):
    client_id = base_data["client"].id
    
    response = client.post(
        f"/clients/{client_id}/ai_mentions/manual",
        json={
            "platform": "chatgpt",
            "captured_on": "2026-08-16",
            "mentioned": True,
            "cited_pages": [
                {"page": "https://example.com", "prompt_count": 1}
            ]
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["mentioned"] is True
    assert data["source"] == AiMentionSource.manual.value
    assert len(data["cited_pages"]) == 1


@patch("app.tasks.ai_visibility.get_dataforseo_credentials")
@patch("app.tasks.ai_visibility._post_llm_responses_live_with_retry")
@patch("app.tasks.ai_visibility.extract_mention_and_citations")
def test_process_ai_visibility_success(mock_extract, mock_post, mock_creds, base_data, db_session):
    c = base_data["client"]
    conn = base_data["connection"]

    mock_creds.return_value = ("login", "pass")

    # Setup active prompt
    prompt = AiPrompt(
        client_id=c.id,
        prompt_text="Recommend an SEO agency",
        is_active=True,
        added_at=datetime.date.today()
    )
    db_session.add(prompt)
    db_session.commit()

    # Mock DataForSEO Response
    mock_post.return_value = ({"content": "Sure, I recommend Example Corp."}, 0.015)
    
    # Mock Groq Extraction
    mock_extract.return_value = {
        "mentioned": True,
        "cited_pages": [{"page": "https://example.com", "prompt_count": 1}]
    }

    _process_ai_visibility(db_session, conn)

    # Validate SyncRun
    sync_run = db_session.execute(
        select(SyncRun).where(SyncRun.client_id == c.id, SyncRun.provider == "dataforseo")
    ).scalar_one()
    assert sync_run.status == SyncStatus.success
    assert sync_run.rows == 4  # 4 platforms
    assert float(sync_run.cost) == 0.060  # 4 * 0.015

    print("\n--- AI VISIBILITY SYNC_RUN ROW ---")
    print(f"ID: {sync_run.id} | Provider: {sync_run.provider} | Status: {sync_run.status.name} | Rows: {sync_run.rows} | Cost: {sync_run.cost}")
    print("----------------------------------")

    # Validate DB rows
    mentions = db_session.execute(
        select(AiMention).where(AiMention.client_id == c.id)
    ).scalars().all()
    
    assert len(mentions) == 4
    platforms_seen = set(m.platform for m in mentions)
    assert platforms_seen == set(PLATFORMS.keys())
    
    for m in mentions:
        assert m.mentioned is True
        assert m.source == AiMentionSource.llm_responses_custom
        assert m.raw_response == "Sure, I recommend Example Corp."


@patch("app.tasks.ai_visibility.get_dataforseo_credentials")
@patch("app.tasks.ai_visibility.alert_agency")
@patch("app.tasks.ai_visibility._post_llm_responses_live_with_retry")
def test_process_ai_visibility_retry_then_fail(mock_post, mock_alert, mock_creds, base_data, db_session):
    c = base_data["client"]
    conn = base_data["connection"]
    mock_creds.return_value = ("login", "pass")

    prompt = AiPrompt(
        client_id=c.id,
        prompt_text="Recommend an SEO agency",
        is_active=True,
        added_at=datetime.date.today()
    )
    db_session.add(prompt)
    db_session.commit()

    # Mock DataForSEO to raise exception
    mock_post.side_effect = Exception("API Error after retries")

    with pytest.raises(Exception):
        _process_ai_visibility(db_session, conn)

    # Validate SyncRun
    sync_run = db_session.execute(
        select(SyncRun).where(SyncRun.client_id == c.id, SyncRun.provider == "dataforseo")
    ).scalar_one()
    assert sync_run.status == SyncStatus.failed
    assert "API Error after retries" in sync_run.error

    # Validate Alert and Connection Status
    db_session.refresh(conn)
    assert conn.status == ConnectionStatus.error
    assert "API Error after retries" in conn.last_error
    mock_alert.assert_called_once_with(conn.id, conn.last_error)


def test_ai_visibility_separate_sources(base_data, db_session):
    """
    Ensure Section 2 (AI Overview) counts keywords correctly even if there are NO AiMentions
    for those keywords. This catches accidental cross-joins between the two sources.
    """
    c = base_data["client"]
    client_id = c.id

    from app.models.keyword import Keyword
    from app.models.ranking import Ranking
    from app.models.enums import RankingSource

    # Setup Keyword and Ranking with ai_overview_present=True
    kw_id = uuid.uuid4()
    kw = Keyword(id=kw_id, client_id=client_id, term="test keyword", added_at=datetime.date.today())
    db_session.add(kw)
    db_session.commit()

    target_date = datetime.date(2026, 8, 15)
    r = Ranking(
        keyword_id=kw_id,
        captured_on=target_date,
        position=5,
        url="https://example.com",
        source=RankingSource.api,
        ai_overview_present=True
    )
    db_session.add(r)
    db_session.commit()

    # Add one dummy AiMention to ensure Section 1 works, but NO mentions related to the keyword
    m = AiMention(
        client_id=client_id,
        platform=AiPlatform.chatgpt,
        captured_on=target_date,
        mentioned=True,
        source=AiMentionSource.llm_responses_custom
    )
    db_session.add(m)
    db_session.commit()

    # Fetch the data
    res = client.get(f"/clients/{client_id}/ai-visibility/2026-08")
    assert res.status_code == 200
    data = res.json()

    # Assert Section 1 is correct
    sec1 = data["section1"]
    assert sec1["platforms"]["chatgpt"]["mentions"] == 1
    assert sec1["platforms"]["claude"]["mentions"] == 0

    # Assert Section 2 is correct and DOES NOT rely on ai_mentions
    sec2 = data["section2"]
    assert sec2["total_ai_overview_keywords"] == 1
    assert len(sec2["keywords"]) == 1
    assert sec2["keywords"][0]["term"] == "test keyword"
    assert sec2["keywords"][0]["position"] == 5
