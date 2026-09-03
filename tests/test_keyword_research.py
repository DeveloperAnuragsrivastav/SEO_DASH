import datetime
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models.account import Account
from app.models.client import Client
from app.models.connection import Connection
from app.models.enums import AccessMode, ClientStatus, ConnectionStatus, ProviderType
from app.models.keyword import Keyword

client = TestClient(app)

@pytest.fixture
def base_data(db_session):
    a = Account(name="Test Account")
    db_session.add(a)
    db_session.flush()

    c = Client(
        account_id=a.id,
        name="Test Client",
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


@patch("app.routes.keyword_research.get_dataforseo_credentials")
@patch("app.routes.keyword_research.fetch_keyword_metrics_with_retry")
def test_keyword_research_success(mock_fetch, mock_creds, base_data, db_session):
    c = base_data["client"]
    mock_creds.return_value = ("login", "pass")
    mock_fetch.return_value = {"search_volume": 12000, "cpc": 2.5, "competition": 0.8, "cost": 0.09}

    response = client.get(f"/clients/{c.id}/keyword-research?term=seo%20tools")
    
    assert response.status_code == 200
    data = response.json()
    assert data["term"] == "seo tools"
    assert data["search_volume"] == 12000
    assert data["cpc"] == 2.5
    assert data["competition"] == 0.8

    from app.models.sync_run import SyncRun
    from app.models.enums import SyncStatus
    
    sync_run = db_session.execute(
        select(SyncRun).where(SyncRun.client_id == c.id, SyncRun.provider == "dataforseo")
    ).scalar_one()
    
    print("\n--- KEYWORD RESEARCH SYNC_RUN ROW ---")
    print(f"ID: {sync_run.id} | Provider: {sync_run.provider} | Status: {sync_run.status.name} | Rows: {sync_run.rows} | Cost: {sync_run.cost}")
    print("-------------------------------------")


@patch("app.routes.keyword_research.get_dataforseo_credentials")
@patch("app.routes.keyword_research.fetch_keyword_metrics_with_retry")
def test_keyword_research_api_failure(mock_fetch, mock_creds, base_data, db_session):
    c = base_data["client"]
    mock_creds.return_value = ("login", "pass")
    mock_fetch.side_effect = Exception("Upstream timeout")

    response = client.get(f"/clients/{c.id}/keyword-research?term=seo%20tools")
    
    assert response.status_code == 502
    assert "Upstream timeout" in response.json()["detail"]


@patch("app.routes.keywords.get_dataforseo_credentials")
@patch("app.routes.keywords.fetch_keyword_metrics_with_retry")
def test_keyword_creation_with_inline_lookup(mock_fetch, mock_creds, base_data, db_session):
    c = base_data["client"]
    mock_creds.return_value = ("login", "pass")
    mock_fetch.return_value = {"search_volume": 45000, "cpc": 1.2, "competition": 0.5}

    response = client.post(
        f"/clients/{c.id}/keywords",
        json={"term": "digital marketing", "fetch_metrics": True}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["term"] == "digital marketing"
    assert data["search_volume"] == 45000
    assert data["is_active"] is True

    # Confirm in DB
    kw = db_session.execute(
        select(Keyword).where(Keyword.client_id == c.id, Keyword.term == "digital marketing")
    ).scalar_one()
    
    assert kw.search_volume == 45000


def test_keyword_creation_without_lookup(base_data, db_session):
    c = base_data["client"]

    response = client.post(
        f"/clients/{c.id}/keywords",
        json={"term": "content strategy"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["term"] == "content strategy"
    assert data["search_volume"] is None

    kw = db_session.execute(
        select(Keyword).where(Keyword.client_id == c.id, Keyword.term == "content strategy")
    ).scalar_one()
    assert kw.search_volume is None


@patch("app.routes.keywords.get_dataforseo_credentials")
@patch("app.routes.keywords.fetch_keyword_metrics_with_retry")
def test_keyword_creation_inline_lookup_fails(mock_fetch, mock_creds, base_data, db_session):
    c = base_data["client"]
    mock_creds.return_value = ("login", "pass")
    mock_fetch.side_effect = Exception("DataForSEO Error")

    response = client.post(
        f"/clients/{c.id}/keywords",
        json={"term": "failing term", "fetch_metrics": True}
    )
    
    assert response.status_code == 502
    assert "DataForSEO Error" in response.json()["detail"]
