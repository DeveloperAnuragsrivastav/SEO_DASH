from __future__ import annotations
import datetime
import threading
import time
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.enums import ReportStatus, MetricSource, ConnectionStatus, ProviderType
from app.models.metric import Metric
from app.models.connection import Connection
from app.models.ranking import Ranking
from app.models.keyword import Keyword
from app.models.report_month import ReportMonth
from app.models.account import Account
from app.models.client import Client
from app.models.ai_mention import AiMention
from app.models.link import Link
from app.models.activity import Activity
from app.models.screenshot import Screenshot
from app.models.enums import LinkStatus
from app.main import app
from fastapi.testclient import TestClient

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
        status="active",
        locale="en-US",
        package_keywords=10,
        onboarded_at=datetime.date.today(),
    )
    db_session.add(c)
    db_session.commit()
    return c


def test_generate_report_concurrency(db_session, base_data):
    """Test that two concurrent requests for the same client and month hit the advisory lock."""
    test_client = base_data
    lock_id = hash(f"{test_client.id}-2026-08") & 0x7FFFFFFFFFFFFFFF
    
    from app.database import engine
    from sqlalchemy import text
    
    with engine.connect() as lock_conn:
        acquired = lock_conn.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id}).scalar()
        assert acquired
        
        # Fire a request while the lock is held
        res = client.post(
            f"/clients/{test_client.id}/reports/generate",
            json={"month": "2026-08-01"}
        )
        assert res.status_code == 409
        assert "in progress" in res.json()["detail"]
        
        lock_conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id})
        lock_conn.commit()
    
    # After lock is released, ensure we can generate (mock the data sources to be safe)
    with patch("app.routes.reports.generate_report_narrative", return_value="Mock"):
        res2 = client.post(
            f"/clients/{test_client.id}/reports/generate",
            json={"month": "2026-08-01"}
        )
        assert res2.status_code == 201

    rows = db_session.execute(select(ReportMonth).where(ReportMonth.client_id == test_client.id)).scalars().all()
    assert len(rows) == 1


def test_data_resolution_hybrid(db_session, base_data):
    """Test the hybrid resolution logic:
    GSC: Connected -> pulls live
    GA4: Not connected -> reads manual
    GBP: Connected but pull fails -> reads manual fallback
    """
    test_client = base_data
    conn_gsc = Connection(client_id=test_client.id, provider=ProviderType.gsc, access_mode="client_owned", status=ConnectionStatus.connected, property_id="sc-domain:example.com")
    conn_gbp = Connection(client_id=test_client.id, provider=ProviderType.gbp, access_mode="client_owned", status=ConnectionStatus.connected, property_id="locations/123")
    db_session.add_all([conn_gsc, conn_gbp])
    
    # Manual data that already exists
    m_ga4 = Metric(client_id=test_client.id, provider="ga4", metric_key="sessions", captured_on=datetime.date(2026, 8, 1), value=400, source=MetricSource.manual)
    m_gbp = Metric(client_id=test_client.id, provider="gbp", metric_key="website_clicks", captured_on=datetime.date(2026, 8, 1), value=50, source=MetricSource.manual)
    db_session.add_all([m_ga4, m_gbp])
    db_session.commit()

    def mock_pull_gsc(db, conn_id, start_date, end_date):
        # Pretend the pull inserted API metrics
        m = Metric(client_id=test_client.id, provider="gsc", metric_key="clicks", captured_on=datetime.date(2026, 8, 1), value=2000, source=MetricSource.api)
        db.add(m)
        db.commit()

    def mock_pull_gbp(*args, **kwargs):
        raise ValueError("GBP API Down")

    with patch("app.routes.reports.pull_gsc_data", side_effect=mock_pull_gsc):
        with patch("app.routes.reports.pull_gbp_data", side_effect=mock_pull_gbp):
            with patch("app.routes.reports.generate_report_narrative", return_value="Mock narrative"):
                res = client.post(
                    f"/clients/{test_client.id}/reports/generate",
                    json={"month": "2026-08-01"}
                )
    
    assert res.status_code == 201
    
    report = db_session.execute(select(ReportMonth).where(ReportMonth.client_id == test_client.id)).scalar_one()
    snap = report.snapshot
    
    # GSC should have the 2000 from the live pull (prioritized over 100 manual)
    assert snap["gsc"]["clicks"] == 2000
    # GA4 should have the 400 from manual (not connected)
    assert snap["ga4"]["sessions"] == 400
    # GBP should have the 50 from manual (connected, but pull failed)
    assert snap["gbp"]["website_clicks"] == 50


def test_derived_figures_rankings(db_session, base_data):
    """Test ranking improvements, declines, and position bands."""
    test_client = base_data
    kw1 = Keyword(client_id=test_client.id, term="term1", added_at=datetime.date.today())
    kw2 = Keyword(client_id=test_client.id, term="term2", added_at=datetime.date.today())
    kw3 = Keyword(client_id=test_client.id, term="term3", added_at=datetime.date.today())
    db_session.add_all([kw1, kw2, kw3])
    db_session.commit()
    
    # Previous month (July)
    r1_old = Ranking(keyword_id=kw1.id, captured_on=datetime.date(2026, 7, 15), position=15, source="api")
    r2_old = Ranking(keyword_id=kw2.id, captured_on=datetime.date(2026, 7, 15), position=5, source="api")
    r3_old = Ranking(keyword_id=kw3.id, captured_on=datetime.date(2026, 7, 15), position=30, source="api")
    
    # Current month (August)
    # kw1 improved from 15 -> 8 (Top 10)
    r1_new = Ranking(keyword_id=kw1.id, captured_on=datetime.date(2026, 8, 15), position=8, source="api")
    # kw2 declined from 5 -> 12 (11-20 band)
    r2_new = Ranking(keyword_id=kw2.id, captured_on=datetime.date(2026, 8, 15), position=12, source="api")
    # kw3 improved from 30 -> 25 (21-50 band)
    r3_new = Ranking(keyword_id=kw3.id, captured_on=datetime.date(2026, 8, 15), position=25, source="api")
    
    # kw4 (new keyword, no history, lands in 51+ band)
    kw4 = Keyword(client_id=test_client.id, term="term4", added_at=datetime.date.today())
    db_session.add(kw4)
    db_session.commit()
    r4_new = Ranking(keyword_id=kw4.id, captured_on=datetime.date(2026, 8, 15), position=55, source="api")
    
    db_session.add_all([r1_old, r2_old, r3_old, r1_new, r2_new, r3_new, r4_new])
    db_session.commit()

    with patch("app.routes.reports.generate_report_narrative", return_value="Mock"):
        res = client.post(
            f"/clients/{test_client.id}/reports/generate",
            json={"month": "2026-08-01"}
        )
    assert res.status_code == 201
    
    report = db_session.execute(select(ReportMonth).where(ReportMonth.client_id == test_client.id)).scalar_one()
    summ = report.snapshot["rankings"]["summary"]
    
    assert summ["improved"] == 2  # kw1, kw3
    assert summ["declined"] == 1  # kw2
    
    assert summ["top_10"] == 1    # kw1 (pos 8)
    assert summ["11_20"] == 1     # kw2 (pos 12)
    assert summ["21_50"] == 1     # kw3 (pos 25)
    assert summ["51_plus"] == 1   # kw4 (pos 55)


def test_publish_flow_and_immutability(db_session, base_data):
    """Test editing narrative, publishing, and rejection of regen on published."""
    test_client = base_data
    # 1. Generate
    with patch("app.routes.reports.generate_report_narrative", return_value="Initial draft"):
        res = client.post(
            f"/clients/{test_client.id}/reports/generate",
            json={"month": "2026-08"}
        )
    assert res.status_code == 201
    
    # 2. Edit narrative (Draft status)
    res_edit = client.put(
        f"/clients/{test_client.id}/reports/2026-08",
        json={"narrative": "Edited draft"}
    )
    assert res_edit.status_code == 200
    assert res_edit.json()["narrative"] == "Edited draft"
    
    # 3. Publish
    res_pub = client.post(f"/clients/{test_client.id}/reports/2026-08/publish")
    assert res_pub.status_code == 200
    
    # 4. Attempt to edit -> 409
    res_edit_fail = client.put(
        f"/clients/{test_client.id}/reports/2026-08",
        json={"narrative": "Try again"}
    )
    assert res_edit_fail.status_code == 409
    
    # 5. Attempt to regen -> 409
    res_regen = client.post(
        f"/clients/{test_client.id}/reports/generate",
        json={"month": "2026-08"}
    )
    assert res_regen.status_code == 409
    assert "already exists" in res_regen.json()["detail"]


@patch("app.services.groq_service.httpx.Client")
@patch("app.services.groq_service.os.environ.get", return_value="fake_key")
def test_narrative_generation(mock_env, mock_httpx, base_data, db_session):
    """Test the narrative prompt structure passed to Groq."""
    test_client = base_data
    mock_instance = mock_httpx.return_value.__enter__.return_value
    mock_instance.post.return_value.json.return_value = {
        "choices": [{"message": {"content": "This is the generated narrative."}}]
    }
    
    res = client.post(
        f"/clients/{test_client.id}/reports/generate",
        json={"month": "2026-08-01"}
    )
    assert res.status_code == 201
    
    # Inspect the payload sent to Groq
    call_kwargs = mock_instance.post.call_args[1]
    payload = call_kwargs["json"]
    messages = payload["messages"]
    
    assert "llama-3.1-8b-instant" in payload["model"]
    assert "draft executive summary" in messages[1]["content"]
    assert test_client.name in messages[1]["content"]
    assert "August 2026" in messages[1]["content"]
    
    print("\n--- GROQ PAYLOAD (Narrative Auto-Draft) ---")
    import json
    print(json.dumps(payload, indent=2))
    print("-------------------------------------------")
    
    # Print Snapshot for User Request Evidence
    report = db_session.execute(select(ReportMonth).where(ReportMonth.client_id == test_client.id)).scalar_one()
    print("\n--- REPORT SNAPSHOT ---")
    print(json.dumps(report.snapshot, indent=2))
    print("-----------------------")
@patch("app.services.groq_service.httpx.Client")
@patch("app.services.groq_service.os.environ.get", return_value="fake_key")
def test_comprehensive_real_data(mock_env, mock_httpx, base_data, db_session):
    """Test full pipeline with REAL data: API prioritizing over Manual, Rankings, AI Mentions, etc."""
    test_client = base_data
    
    # Setup Connections
    conn_gsc = Connection(client_id=test_client.id, provider=ProviderType.gsc, access_mode="client_owned", status=ConnectionStatus.connected, property_id="sc-domain:example.com")
    conn_ga4 = Connection(client_id=test_client.id, provider=ProviderType.ga4, access_mode="client_owned", status=ConnectionStatus.connected, property_id="properties/123")
    db_session.add_all([conn_gsc, conn_ga4])
    db_session.commit()
    
    # Setup Metrics - Mix of API and Manual
    # GSC: manual on 8/1, mock API on 8/2
    m_gsc_manual = Metric(client_id=test_client.id, provider="gsc", metric_key="clicks", captured_on=datetime.date(2026, 8, 1), value=15, source=MetricSource.manual)
    # GA4: manual only
    m_ga4_manual_1 = Metric(client_id=test_client.id, provider="ga4", metric_key="sessions", captured_on=datetime.date(2026, 8, 1), value=400, source=MetricSource.manual)
    m_ga4_manual_2 = Metric(client_id=test_client.id, provider="ga4", metric_key="sessions", captured_on=datetime.date(2026, 8, 2), value=600, source=MetricSource.manual)
    db_session.add_all([m_gsc_manual, m_ga4_manual_1, m_ga4_manual_2])
    db_session.commit()
    
    # Setup Keywords and Rankings
    kw1 = Keyword(client_id=test_client.id, term="term1", added_at=datetime.date.today())
    kw2 = Keyword(client_id=test_client.id, term="term2", added_at=datetime.date.today())
    kw3 = Keyword(client_id=test_client.id, term="term3", added_at=datetime.date.today())
    db_session.add_all([kw1, kw2, kw3])
    db_session.commit()
    
    # Prev Rankings
    r1_old = Ranking(keyword_id=kw1.id, captured_on=datetime.date(2026, 7, 15), position=15, source="api")
    r2_old = Ranking(keyword_id=kw2.id, captured_on=datetime.date(2026, 7, 15), position=5, source="api")
    r3_old = Ranking(keyword_id=kw3.id, captured_on=datetime.date(2026, 7, 15), position=55, source="api")
    
    # New Rankings
    r1_new = Ranking(keyword_id=kw1.id, captured_on=datetime.date(2026, 8, 15), position=8, source="api") # 15 -> 8 (Improved, Top 10)
    r2_new = Ranking(keyword_id=kw2.id, captured_on=datetime.date(2026, 8, 15), position=12, source="api") # 5 -> 12 (Declined, 11-20)
    r3_new = Ranking(keyword_id=kw3.id, captured_on=datetime.date(2026, 8, 15), position=25, source="api") # 55 -> 25 (Improved, 21-50)
    db_session.add_all([r1_old, r2_old, r3_old, r1_new, r2_new, r3_new])
    db_session.commit()
    
    # Setup AI Mention
    from app.models.enums import AiPlatform, AiMentionSource
    aim = AiMention(client_id=test_client.id, platform=AiPlatform.chatgpt, captured_on=datetime.date(2026, 8, 10), mentioned=True, source=AiMentionSource.llm_responses_custom)
    db_session.add(aim)
    db_session.commit()
    # Seed previous month's metrics so deltas are actually computed dynamically
    m_gsc_prev = Metric(client_id=test_client.id, provider="gsc", metric_key="clicks", captured_on=datetime.date(2026, 7, 15), value=80, source=MetricSource.manual)
    m_ga4_prev = Metric(client_id=test_client.id, provider="ga4", metric_key="sessions", captured_on=datetime.date(2026, 7, 15), value=850, source=MetricSource.manual)
    db_session.add_all([m_gsc_prev, m_ga4_prev])
    db_session.commit()
    
    def mock_pull_gsc(db, conn_id, start_date, end_date):
        m = Metric(client_id=test_client.id, provider="gsc", metric_key="clicks", captured_on=datetime.date(2026, 8, 2), value=120, source=MetricSource.api)
        db.add(m)
        db.commit()

    def mock_pull_ga4(*args, **kwargs):
        raise ValueError("GA4 fail")

    # Mock Groq narrative
    mock_instance = mock_httpx.return_value.__enter__.return_value
    mock_instance.post.return_value.json.return_value = {
        "choices": [{"message": {"content": "This is a real-data executive summary generated by Groq."}}]
    }
    
    with patch("app.routes.reports.pull_gsc_data", side_effect=mock_pull_gsc):
        with patch("app.routes.reports.pull_ga4_data", side_effect=mock_pull_ga4):
            res = client.post(
                f"/clients/{test_client.id}/reports/generate",
                json={"month": "2026-08-01"}
            )
            assert res.status_code == 201

    row = db_session.execute(select(ReportMonth).where(ReportMonth.client_id == test_client.id, ReportMonth.month == datetime.date(2026, 8, 1))).scalar_one()
    snap = row.snapshot
    
    # Print it out for the user
    import json
    print("\\n\\n--- COMPREHENSIVE SNAPSHOT ---")
    print(json.dumps(snap, indent=2))
    print("------------------------------\\n")
    print(f"--- NARRATIVE ---\\n{row.narrative}\\n-----------------\\n")
    
    # Assertions on resolution logic
    assert snap["gsc"]["clicks"] == 120  # API prioritized, ignored manual 15
    assert snap["ga4"]["sessions"] == 1000 # Manual fallback used (400 + 600)
    
    # Assertions on deltas
    assert snap["kpi_deltas"]["gsc"]["clicks"] == 40.0 # 120 - 80
    assert snap["kpi_deltas"]["ga4"]["sessions"] == 150.0 # 1000 - 850
    
    # Assertions on rankings logic
    assert snap["rankings"]["summary"]["improved"] == 2
    assert snap["rankings"]["summary"]["declined"] == 1
    assert snap["rankings"]["summary"]["top_10"] == 1
    assert snap["rankings"]["summary"]["11_20"] == 1
    assert snap["rankings"]["summary"]["21_50"] == 1
    
    # Assertions on AI logic
    assert len(snap["ai_visibility"]) == 1
    assert snap["ai_visibility"][0]["platform"] == "chatgpt"
