from __future__ import annotations
import datetime
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import select

from app.models.cost import DailyProviderCost, ProviderState
from app.tasks.cost_guardrail import aggregate_daily_cost, _check_cost_guardrail
from app.tasks.rankings import trigger_nightly_rankings_pull
from app.config import settings


@pytest.fixture
def mock_settings():
    # Store old values
    old_multiplier = settings.COST_GUARDRAIL_MULTIPLIER
    old_min_days = settings.COST_GUARDRAIL_MIN_DAYS
    old_floor = settings.COST_GUARDRAIL_FLOOR_USD
    
    # Configure test settings
    settings.COST_GUARDRAIL_MULTIPLIER = 3.0
    settings.COST_GUARDRAIL_MIN_DAYS = 3
    settings.COST_GUARDRAIL_FLOOR_USD = 5.0
    
    yield settings
    
    # Restore
    settings.COST_GUARDRAIL_MULTIPLIER = old_multiplier
    settings.COST_GUARDRAIL_MIN_DAYS = old_min_days
    settings.COST_GUARDRAIL_FLOOR_USD = old_floor


def test_guardrail_normal_day(db_session, mock_settings):
    """Test a normal day that is below the threshold."""
    provider = "dataforseo"
    today = datetime.date.today()
    
    # Setup history (3 days at $10/day)
    for i in range(1, 4):
        db_session.add(DailyProviderCost(date=today - datetime.timedelta(days=i), provider=provider, cost=10.0))
    db_session.commit()
    
    # Current cost is $25 (limit is 10 * 3.0 = 30)
    with patch("app.tasks.cost_guardrail.alert_agency") as mock_alert:
        _check_cost_guardrail(db_session, provider, today, 25.0)
        
        # No alert, no pause
        mock_alert.assert_not_called()
        
        state = db_session.execute(select(ProviderState).where(ProviderState.provider == provider)).scalar_one_or_none()
        assert state is None or not state.is_paused


def test_guardrail_breach_day(db_session, mock_settings):
    """Test a day that exceeds the rolling average threshold."""
    provider = "dataforseo"
    today = datetime.date.today()
    
    # Setup history (3 days at $10/day)
    for i in range(1, 4):
        db_session.add(DailyProviderCost(date=today - datetime.timedelta(days=i), provider=provider, cost=10.0))
    db_session.commit()
    
    # Current cost is $35 (limit is 10 * 3.0 = 30) -> Breach
    with patch("app.tasks.cost_guardrail.alert_agency") as mock_alert:
        _check_cost_guardrail(db_session, provider, today, 35.0)
        
        # Alert should be called
        mock_alert.assert_called_once()
        assert "PAUSED" in mock_alert.call_args[1]["message"]
        assert "$35" in mock_alert.call_args[1]["message"]
        assert "$30" in mock_alert.call_args[1]["message"]
        
        # Query the DB for the daily history
        history = db_session.execute(select(DailyProviderCost).where(DailyProviderCost.provider == provider)).scalars().all()
        avg = sum(float(h.cost) for h in history) / len(history)
        threshold = avg * mock_settings.COST_GUARDRAIL_MULTIPLIER
        
        # Pause state should be True
        state = db_session.execute(select(ProviderState).where(ProviderState.provider == provider)).scalar_one()
        assert state.is_paused is True
        assert state.paused_at is not None

        print("\n--- DB ROWS: BREACH DETECTION ---")
        print(f"Daily Cost Aggregation Result (Current Spend Attempt): $35.00")
        print(f"Computed Rolling Average (3 days): ${avg:.2f}")
        print(f"Threshold Value Used (Avg * 3.0): ${threshold:.2f}")
        print(f"Resulting Pause-Flag State: {state.is_paused} at {state.paused_at}")
        print("---------------------------------")


def test_guardrail_edge_case_first_days(db_session, mock_settings):
    """Test the first days of operation when there is insufficient history (< 3 days)."""
    provider = "dataforseo"
    today = datetime.date.today()
    
    # Setup history: only 1 day of history at $1.00 (avg = 1.00)
    db_session.add(DailyProviderCost(date=today - datetime.timedelta(days=1), provider=provider, cost=1.0))
    db_session.commit()
    
    # Floor is $5.0. Limit is Floor(5) * Multiplier(3) = 15.0
    # Current cost is $12.0 (breaches raw avg of 3.0, but not floor-based limit of 15.0)
    with patch("app.tasks.cost_guardrail.alert_agency") as mock_alert:
        _check_cost_guardrail(db_session, provider, today, 12.0)
        
        # No alert, no pause because floor protected it
        mock_alert.assert_not_called()


def test_rankings_gate_blocks_on_pause(db_session, mock_settings):
    """Test that the rankings job aborts immediately if the provider is paused."""
    provider = "dataforseo"
    
    # Set the provider state to paused
    db_session.add(ProviderState(provider=provider, is_paused=True, paused_at=datetime.datetime.now(datetime.timezone.utc)))
    db_session.commit()
    
    with patch("app.tasks.rankings._process_connection") as mock_process:
        with patch("app.tasks.rankings.logger.error") as mock_logger:
            mock_session_local = MagicMock()
            mock_session_local.return_value.__enter__.return_value = db_session
            with patch("app.tasks.rankings.SessionLocal", mock_session_local):
                trigger_nightly_rankings_pull()
            
            # Should have logged the abort
            mock_logger.assert_called_once_with("Rankings job aborted: Provider 'dataforseo' is PAUSED due to cost guardrail.")
            # Should NOT have processed any connections
            mock_process.assert_not_called()
