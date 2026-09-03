import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.main import app

client = TestClient(app)


@pytest.fixture
def test_client_id(db_session: Session) -> uuid.UUID:
    """Insert a test account and client, return client_id."""
    account_id = uuid.uuid4()
    client_id = uuid.uuid4()

    db_session.execute(
        text("INSERT INTO accounts (id, name) VALUES (:id, 'Test Account')"),
        {"id": str(account_id)},
    )
    db_session.execute(
        text(
            "INSERT INTO clients (id, account_id, name, domain, business_type, "
            "locale, package_keywords, status, onboarded_at) "
            "VALUES (:id, :aid, 'Test Client', 'test.com', 'ecommerce', 'en', 10, 'active', '2026-01-01')"
        ),
        {"id": str(client_id), "aid": str(account_id)},
    )
    db_session.commit()
    return client_id


def test_manual_gsc_success(test_client_id: uuid.UUID, db_session: Session) -> None:
    payload = {
        "records": [
            {
                "captured_on": "2026-08-01",
                "clicks": 100,
                "impressions": 500,
                "ctr": 0.2,
                "position": 5.5,
            },
            {
                "captured_on": "2026-08-01",
                "clicks": 50,
                "impressions": 1000,
                "ctr": 0.05,
                "position": 12.1,
                "dimension_key": "page",
                "dimension_value": "https://test.com/about",
            },
        ]
    }

    response = client.post(f"/clients/{test_client_id}/manual-gsc", json=payload)
    assert response.status_code == 201

    # 2 records, each with 4 metrics -> 8 metrics total
    assert response.json()["rows_inserted"] == 8

    # Verify DB
    res = db_session.execute(
        text("SELECT COUNT(*) FROM metrics WHERE client_id = :cid AND source = 'manual'"),
        {"cid": str(test_client_id)},
    ).scalar()
    assert res == 8


def test_manual_gsc_validation_errors(test_client_id: uuid.UUID) -> None:
    # Negative clicks
    payload1 = {
        "records": [
            {
                "captured_on": "2026-08-01",
                "clicks": -10,
                "impressions": 500,
                "ctr": 0.2,
                "position": 5.5,
            }
        ]
    }
    response1 = client.post(f"/clients/{test_client_id}/manual-gsc", json=payload1)
    assert response1.status_code == 422
    assert "clicks" in str(response1.json()["detail"])

    # CTR > 1.0
    payload2 = {
        "records": [
            {
                "captured_on": "2026-08-01",
                "clicks": 10,
                "impressions": 500,
                "ctr": 1.2,
                "position": 5.5,
            }
        ]
    }
    response2 = client.post(f"/clients/{test_client_id}/manual-gsc", json=payload2)
    assert response2.status_code == 422
    assert "ctr" in str(response2.json()["detail"])

    # Position < 0
    payload3 = {
        "records": [
            {
                "captured_on": "2026-08-01",
                "clicks": 10,
                "impressions": 500,
                "ctr": 0.5,
                "position": -5.5,
            }
        ]
    }
    response3 = client.post(f"/clients/{test_client_id}/manual-gsc", json=payload3)
    assert response3.status_code == 422
    assert "position" in str(response3.json()["detail"])


def test_manual_gsc_malformed(test_client_id: uuid.UUID) -> None:
    # Missing required field
    payload = {
        "records": [
            {
                "clicks": 10,
                "impressions": 500,
            }
        ]
    }
    response = client.post(f"/clients/{test_client_id}/manual-gsc", json=payload)
    assert response.status_code == 422
    assert "captured_on" in str(response.json()["detail"])
    assert "ctr" in str(response.json()["detail"])
    assert "position" in str(response.json()["detail"])


def test_manual_ga4_success(test_client_id: uuid.UUID, db_session: Session) -> None:
    payload = {
        "records": [
            {
                "captured_on": "2026-08-01",
                "sessions": 500,
                "users": 450,
                "engaged_sessions": 300,
                "conversions": 25,
                "revenue": 1500.50,
            },
            {
                "captured_on": "2026-08-01",
                "sessions": 300,
                "users": 270,
                "engaged_sessions": 180,
                "conversions": 15,
                "revenue": 900.0,
                "dimension_key": "country",
                "dimension_value": "United States",
            }
        ]
    }

    response = client.post(f"/clients/{test_client_id}/manual-ga4", json=payload)
    assert response.status_code == 201
    assert response.json() == {"status": "success", "rows_inserted": 10}

    # Verify all 10 rows (5 per record)
    res = db_session.execute(
        text("SELECT COUNT(*) FROM metrics WHERE client_id = :cid AND provider = 'ga4' AND source = 'manual'"),
        {"cid": str(test_client_id)},
    ).scalar()
    assert res == 10

    # Verify exact row values for a specific record
    metric_record = db_session.execute(
        text(
            "SELECT value FROM metrics WHERE client_id = :cid AND provider = 'ga4' "
            "AND metric_key = 'revenue' AND dimension_key = 'country'"
        ),
        {"cid": str(test_client_id)},
    ).scalar()
    assert metric_record is not None
    assert float(metric_record) == 900.0


def test_manual_ga4_validation_errors(test_client_id: uuid.UUID) -> None:
    # Negative values
    payload = {
        "records": [
            {
                "captured_on": "2026-08-01",
                "sessions": -5,
                "users": 450,
                "engaged_sessions": 300,
                "conversions": 25,
                "revenue": -10.0,
            }
        ]
    }
    response = client.post(f"/clients/{test_client_id}/manual-ga4", json=payload)
    assert response.status_code == 422
    assert "sessions" in str(response.json()["detail"])
    assert "revenue" in str(response.json()["detail"])


def test_manual_ga4_malformed(test_client_id: uuid.UUID) -> None:
    # Missing required field
    payload = {
        "records": [
            {
                "sessions": 500,
                "users": 450,
            }
        ]
    }
    response = client.post(f"/clients/{test_client_id}/manual-ga4", json=payload)
    assert response.status_code == 422
    assert "captured_on" in str(response.json()["detail"])
    assert "revenue" in str(response.json()["detail"])


def test_manual_gbp_success(test_client_id: uuid.UUID, db_session: Session) -> None:
    payload = {
        "records": [
            {
                "captured_on": "2026-07-15",
                "impressions_desktop_maps": 120,
                "impressions_desktop_search": 350,
                "impressions_mobile_maps": 480,
                "impressions_mobile_search": 610,
                "calls": 25,
                "direction_requests": 42,
                "website_clicks": 88,
                "bookings": 7,
            }
        ]
    }

    response = client.post(f"/clients/{test_client_id}/manual-gbp", json=payload)
    assert response.status_code == 201
    assert response.json() == {"status": "success", "rows_inserted": 8}

    # Verify all 8 rows in DB
    res = db_session.execute(
        text(
            "SELECT COUNT(*) FROM metrics WHERE client_id = :cid "
            "AND provider = 'gbp' AND source = 'manual'"
        ),
        {"cid": str(test_client_id)},
    ).scalar()
    assert res == 8

    # Verify each metric value
    rows = db_session.execute(
        text(
            "SELECT metric_key, value FROM metrics WHERE client_id = :cid "
            "AND provider = 'gbp' AND source = 'manual'"
        ),
        {"cid": str(test_client_id)},
    ).fetchall()

    print("\n--- ACTUAL GBP MANUAL DB ROWS (ALL 8 METRICS) ---")
    metric_dict = {}
    for row in rows:
        print(f"metric_key={row[0]} | value={row[1]}")
        metric_dict[row[0]] = float(row[1])
    print("-------------------------------------------------")

    assert metric_dict["impressions_desktop_maps"] == 120.0
    assert metric_dict["impressions_desktop_search"] == 350.0
    assert metric_dict["impressions_mobile_maps"] == 480.0
    assert metric_dict["impressions_mobile_search"] == 610.0
    assert metric_dict["calls"] == 25.0
    assert metric_dict["direction_requests"] == 42.0
    assert metric_dict["website_clicks"] == 88.0
    assert metric_dict["bookings"] == 7.0


def test_manual_gbp_validation_errors(test_client_id: uuid.UUID) -> None:
    payload = {
        "records": [
            {
                "captured_on": "2026-07-15",
                "impressions_desktop_maps": -5,
                "impressions_desktop_search": 350,
                "impressions_mobile_maps": 480,
                "impressions_mobile_search": 610,
                "calls": -1,
                "direction_requests": 42,
                "website_clicks": 88,
                "bookings": 7,
            }
        ]
    }
    response = client.post(f"/clients/{test_client_id}/manual-gbp", json=payload)
    assert response.status_code == 422
    assert "impressions_desktop_maps" in str(response.json()["detail"])
    assert "calls" in str(response.json()["detail"])


def test_manual_gbp_malformed(test_client_id: uuid.UUID) -> None:
    # Missing required fields
    payload = {
        "records": [
            {
                "captured_on": "2026-07-15",
                "impressions_desktop_maps": 120,
            }
        ]
    }
    response = client.post(f"/clients/{test_client_id}/manual-gbp", json=payload)
    assert response.status_code == 422
    assert "calls" in str(response.json()["detail"])
    assert "website_clicks" in str(response.json()["detail"])

