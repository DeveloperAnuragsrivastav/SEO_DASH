from __future__ import annotations
import datetime
import logging
from decimal import Decimal

from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.models.connection import Connection
from app.models.cost import DailyProviderCost, ProviderState
from app.models.provider_task import ProviderTask
from app.models.sync_run import SyncRun

logger = logging.getLogger(__name__)


from app.utils.alerting import send_email_alert

def alert_agency(subject: str, message: str):
    """Alerts agency on Slack/Email. Phase 7 gap."""
    send_email_alert(subject, message)


@celery_app.task(name="aggregate_daily_cost")
def aggregate_daily_cost(target_date_str: str | None = None):
    """
    Computes daily cost per provider, upserts to daily_provider_costs,
    and runs the cost guardrail check.
    """
    if target_date_str:
        target_date = datetime.date.fromisoformat(target_date_str)
    else:
        target_date = datetime.date.today()

    with SessionLocal() as db:
        # Sum from provider_tasks (e.g. rankings)
        provider_tasks_costs = (
            db.query(
                Connection.provider,
                func.sum(ProviderTask.cost).label("total_cost")
            )
            .join(Connection, ProviderTask.connection_id == Connection.id)
            .filter(func.date(ProviderTask.submitted_at) == target_date)
            .group_by(Connection.provider)
            .all()
        )

        # Sum from sync_runs (e.g. AI visibility, keywords)
        sync_runs_costs = (
            db.query(
                SyncRun.provider,
                func.sum(SyncRun.cost).label("total_cost")
            )
            .filter(func.date(SyncRun.started_at) == target_date)
            .group_by(SyncRun.provider)
            .all()
        )

        # Merge costs
        daily_totals: dict[str, float] = {}
        for provider, cost in provider_tasks_costs:
            if cost:
                daily_totals[provider] = daily_totals.get(provider, 0.0) + float(cost)
        
        for provider, cost in sync_runs_costs:
            if cost:
                daily_totals[provider] = daily_totals.get(provider, 0.0) + float(cost)

        for provider, total_cost in daily_totals.items():
            # Upsert into daily_provider_costs
            daily_cost_record = db.execute(
                select(DailyProviderCost)
                .where(DailyProviderCost.date == target_date, DailyProviderCost.provider == provider)
            ).scalar_one_or_none()

            if not daily_cost_record:
                daily_cost_record = DailyProviderCost(date=target_date, provider=provider, cost=total_cost)
                db.add(daily_cost_record)
            else:
                daily_cost_record.cost = total_cost

            db.commit()

            # Run Guardrail Check
            _check_cost_guardrail(db, provider, target_date, total_cost)


def _check_cost_guardrail(db: Session, provider: str, current_date: datetime.date, current_cost: float):
    """
    Checks if today's cost exceeds the guardrail limit for the provider.
    """
    start_date = current_date - datetime.timedelta(days=14)
    end_date = current_date - datetime.timedelta(days=1)

    historical_costs = db.execute(
        select(DailyProviderCost.cost)
        .where(
            DailyProviderCost.provider == provider,
            DailyProviderCost.date >= start_date,
            DailyProviderCost.date <= end_date,
        )
    ).scalars().all()

    days_history = len(historical_costs)
    if days_history == 0:
        rolling_avg = 0.0
    else:
        rolling_avg = sum(float(c) for c in historical_costs) / days_history

    # Edge Case: Fallback if not enough history
    if days_history < settings.COST_GUARDRAIL_MIN_DAYS:
        logger.info(f"Guardrail for {provider}: Only {days_history} days history. Using floor baseline.")
        baseline = max(rolling_avg, settings.COST_GUARDRAIL_FLOOR_USD)
    else:
        baseline = rolling_avg

    limit = baseline * settings.COST_GUARDRAIL_MULTIPLIER

    if current_cost > limit:
        logger.error(
            f"GUARDRAIL BREACH: {provider} spent ${current_cost:.2f} today, exceeding limit of ${limit:.2f} "
            f"(avg: ${rolling_avg:.2f}, multiplier: {settings.COST_GUARDRAIL_MULTIPLIER})."
        )
        
        # Pause the provider
        provider_state = db.execute(
            select(ProviderState).where(ProviderState.provider == provider)
        ).scalar_one_or_none()

        if not provider_state:
            provider_state = ProviderState(provider=provider, is_paused=True, paused_at=datetime.datetime.now(datetime.timezone.utc))
            db.add(provider_state)
        else:
            provider_state.is_paused = True
            provider_state.paused_at = datetime.datetime.now(datetime.timezone.utc)
        
        db.commit()

        # Alert the agency
        alert_agency(
            subject="Cost Guardrail Breach Detected",
            message=f"Provider {provider} has been PAUSED. Spend: ${current_cost:.2f} | Limit: ${limit:.2f}"
        )
