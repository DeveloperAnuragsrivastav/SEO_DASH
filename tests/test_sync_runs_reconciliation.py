from __future__ import annotations
import datetime
import uuid
from unittest.mock import patch

from app.models.account import Account
from app.models.client import Client
from app.models.connection import Connection
from app.models.enums import AccessMode, ClientStatus, ConnectionStatus, ProviderType, SyncStatus, TaskStatus
from app.models.provider_task import ProviderTask
from app.models.sync_run import SyncRun
from app.tasks.rankings import reconcile_sync_runs


def _setup_base_data(db_session):
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

    sync_run = SyncRun(
        client_id=c.id,
        provider="dataforseo_serp",
        started_at=datetime.datetime.now(datetime.timezone.utc),
        status=SyncStatus.partial,
        rows=2,
    )
    db_session.add(sync_run)
    db_session.flush()

    return conn, sync_run


@patch("app.tasks.rankings.SessionLocal")
def test_all_tasks_completed_success(mock_session_local, db_session):
    conn, sync_run = _setup_base_data(db_session)
    mock_session_local.return_value.__enter__.return_value = db_session

    ptask1 = ProviderTask(
        connection_id=conn.id,
        task_id="t1",
        tag="tag1",
        status=TaskStatus.completed,
        submitted_at=datetime.datetime.now(datetime.timezone.utc),
        sync_run_id=sync_run.id
    )
    ptask2 = ProviderTask(
        connection_id=conn.id,
        task_id="t2",
        tag="tag2",
        status=TaskStatus.completed,
        submitted_at=datetime.datetime.now(datetime.timezone.utc),
        sync_run_id=sync_run.id
    )
    db_session.add_all([ptask1, ptask2])
    db_session.commit()

    reconcile_sync_runs()

    db_session.refresh(sync_run)
    assert sync_run.status == SyncStatus.success


@patch("app.tasks.rankings.alert_agency")
@patch("app.tasks.rankings.SessionLocal")
def test_staleness_path_failed(mock_session_local, mock_alert_agency, db_session):
    conn, sync_run = _setup_base_data(db_session)
    mock_session_local.return_value.__enter__.return_value = db_session

    stale_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=130)

    ptask1 = ProviderTask(
        connection_id=conn.id,
        task_id="t1",
        tag="tag1",
        status=TaskStatus.pending,
        submitted_at=stale_time,
        sync_run_id=sync_run.id
    )
    ptask2 = ProviderTask(
        connection_id=conn.id,
        task_id="t2",
        tag="tag2",
        status=TaskStatus.completed,
        submitted_at=datetime.datetime.now(datetime.timezone.utc),
        sync_run_id=sync_run.id
    )
    db_session.add_all([ptask1, ptask2])
    db_session.commit()

    reconcile_sync_runs()

    db_session.refresh(sync_run)
    db_session.refresh(ptask1)
    db_session.refresh(conn)

    assert ptask1.status == TaskStatus.failed
    assert conn.status == ConnectionStatus.error
    assert "120 minutes" in conn.last_error
    mock_alert_agency.assert_called_once_with(conn.id, f"DataForSEO task t1 stalled and timed out after 120 minutes.")
    
    assert sync_run.status == SyncStatus.partial  # One failed, one completed -> mixed state


@patch("app.tasks.rankings.SessionLocal")
def test_pending_tasks_within_threshold_partial(mock_session_local, db_session):
    conn, sync_run = _setup_base_data(db_session)
    mock_session_local.return_value.__enter__.return_value = db_session

    recent_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=60)

    ptask1 = ProviderTask(
        connection_id=conn.id,
        task_id="t1",
        tag="tag1",
        status=TaskStatus.pending,
        submitted_at=recent_time,
        sync_run_id=sync_run.id
    )
    db_session.add(ptask1)
    db_session.commit()

    reconcile_sync_runs()

    db_session.refresh(sync_run)
    db_session.refresh(ptask1)

    assert ptask1.status == TaskStatus.pending
    assert sync_run.status == SyncStatus.partial


@patch("app.tasks.rankings.SessionLocal")
def test_mixed_state_resolved_partial(mock_session_local, db_session):
    conn, sync_run = _setup_base_data(db_session)
    mock_session_local.return_value.__enter__.return_value = db_session

    ptask1 = ProviderTask(
        connection_id=conn.id,
        task_id="t1",
        tag="tag1",
        status=TaskStatus.failed,
        submitted_at=datetime.datetime.now(datetime.timezone.utc),
        sync_run_id=sync_run.id
    )
    ptask2 = ProviderTask(
        connection_id=conn.id,
        task_id="t2",
        tag="tag2",
        status=TaskStatus.completed,
        submitted_at=datetime.datetime.now(datetime.timezone.utc),
        sync_run_id=sync_run.id
    )
    db_session.add_all([ptask1, ptask2])
    db_session.commit()

    reconcile_sync_runs()

    db_session.refresh(sync_run)
    assert sync_run.status == SyncStatus.partial
