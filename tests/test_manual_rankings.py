from __future__ import annotations
import datetime
import io

from fastapi.testclient import TestClient

from app.main import app
from app.models.client import Client
from app.models.enums import ClientStatus, RankingSource
from app.models.keyword import Keyword
from app.models.ranking import Ranking

client = TestClient(app)


def test_upload_csv_rankings(db_session):
    """Test manual ranking CSV upload."""
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

    kw = Keyword(client_id=c.id, term="test kw", added_at=datetime.date.today())
    db_session.add(kw)
    db_session.commit()

    # Valid CSV content
    csv_content = (
        "keyword,position,date,url\n"
        "test kw,5,2025-01-15,https://example.com\n"
        "missing kw,10,2025-01-15,https://example.com\n"  # Should fail, not tracked
        "test kw,invalid,2025-01-15,https://example.com\n"  # Should fail, invalid pos
    )
    file_obj = io.BytesIO(csv_content.encode("utf-8"))

    response = client.post(
        f"/clients/{c.id}/rankings/upload_csv",
        files={"file": ("test.csv", file_obj, "text/csv")},
    )
    
    assert response.status_code == 201
    data = response.json()
    
    assert data["rows_inserted"] == 1
    assert data["status"] == "partial"
    assert len(data["errors"]) == 2

    # Verify db
    ranking = db_session.query(Ranking).filter_by(keyword_id=kw.id).first()
    assert ranking is not None
    assert ranking.position == 5
    assert ranking.url == "https://example.com"
    assert ranking.source == RankingSource.manual


def test_manual_entry_form(db_session):
    """Test single ranking entry form."""
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

    kw = Keyword(client_id=c.id, term="test kw", added_at=datetime.date.today())
    db_session.add(kw)
    db_session.commit()

    payload = {
        "keyword_id": str(kw.id),
        "captured_on": "2025-02-01",
        "position": 2,
        "url": "https://example.com/2"
    }

    response = client.post(f"/clients/{c.id}/rankings/manual", json=payload)
    assert response.status_code == 201

    ranking = db_session.query(Ranking).filter_by(keyword_id=kw.id).first()
    assert ranking is not None
    assert ranking.position == 2
    assert ranking.url == "https://example.com/2"
    assert ranking.source == RankingSource.manual
