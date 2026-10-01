from __future__ import annotations
import datetime
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request, File, UploadFile, Response
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.database import get_db
from app.models.ai_prompt import AiPrompt
from app.models.client import Client
from app.models.connection import Connection
from app.models.enums import AiPlatform, ConnectionStatus, ProviderType, ReportStatus
from app.models.keyword import Keyword
from app.models.metric import Metric
from app.models.report_snapshot import ReportSnapshot
from app.models.report_image import ReportImage
from app.services import report_composer as composer
from app.services import report_text
from app.services.openai_service import suggest_report_sections
from app.services.openai_service import generate_section_summaries
from app.services.openai_service import generate_next_plan
from app.services.openai_service import generate_slide_subtitles
from app.services import report_period as periods_svc
from calendar import monthrange

def get_month_boundaries(year: int, month: int) -> tuple[datetime.date, datetime.date]:
    _, last_day = monthrange(year, month)
    return datetime.date(year, month, 1), datetime.date(year, month, last_day)

logger = logging.getLogger(__name__)

from app.dependencies import RequireRole
from app.models.enums import UserRole

router = APIRouter(
    prefix="/clients/{client_id}/reports",
    tags=["reports"],
    dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))]
)


class ReportGenerateRequest(BaseModel):
    month: datetime.date


class ReportUpdateNarrativeRequest(BaseModel):
    narrative: str


class ReportHistoryResponse(BaseModel):
    id: uuid.UUID
    start_date: datetime.date
    end_date: datetime.date
    status: ReportStatus
    generated_at: datetime.datetime | None
    published_at: datetime.datetime | None
    
    model_config = {"from_attributes": True}


@router.post("/generate")
def generate_report(
    client_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    data: Optional[GenerateRequest] = None,
    db: Session = Depends(get_db),
):
    """Generate the report for the last finished month, optionally combined
    with the published months before it.

    Only that month (and the one before, for its comparison) is pulled from
    Google. One report per month: September's is made in October, and once it
    is published the next opens on 1 November.
    """
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found.")

    anchor = periods_svc.anchor_for(db, client_id)
    if anchor["mode"] == "locked":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(f"{anchor['anchor_end']:%B}'s report is published. The next report opens on the 1st of next month "
                    f"— in {anchor['days_remaining']} day{'s' if anchor['days_remaining'] != 1 else ''}."),
        )
    if anchor["mode"] == "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This cycle already has a draft report — open it to change how many months it covers.",
        )

    months = data.months if data else 1
    available = len(periods_svc.timeline(db, client_id, anchor["anchor_end"]))
    if months < 1 or months > available:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {available} month{'s' if available != 1 else ''} of data can be combined for this client.",
        )

    # Dispatch to BackgroundTasks instead of Celery (since Railway doesn't run a Celery worker by default)
    from app.tasks.reports import generate_snapshot_report

    task_id = str(uuid.uuid4())
    # The month the checks above were made for — never "yesterday", which
    # mid-month would start a report for the month still under way.
    background_tasks.add_task(generate_snapshot_report, str(client_id), months, anchor["anchor_end"])

    return {
        "status": "processing",
        "task_id": task_id,
        "months": months,
        "message": "Report generation has been queued."
    }


@router.put("/{snapshot_id}")
def update_report_narrative(client_id: uuid.UUID, snapshot_id: uuid.UUID, payload: ReportUpdateNarrativeRequest, db: Session = Depends(get_db)):
    """Edit the narrative of a draft/review report."""
    report = db.execute(
        select(ReportSnapshot).where(ReportSnapshot.client_id == client_id, ReportSnapshot.id == snapshot_id)
    ).scalar_one_or_none()
    
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
        
    if report.status == ReportStatus.published:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot edit a published report.")
        
    report.narrative = payload.narrative
    db.commit()
    
    return {"status": "success", "narrative": report.narrative}


from app.models.user import User
from app.dependencies import get_current_user

# Anyone who can open the client's report may publish it (the router already
# checks they are assigned to the client). Correcting a published month stays
# with a super admin, on the sheets.
@router.post("/{snapshot_id}/publish")
def publish_report(client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Publish the report."""
    report = _load_draft(client_id, snapshot_id, db, lock=True)
    if report.status == ReportStatus.published:
        raise HTTPException(status.HTTP_409_CONFLICT, "Report is already published.")
    months = ((report.snapshot or {}).get("period") or {}).get("months") or 1
    from app.services import sheets
    month = sheets.report_month(report)
    # A month belongs to one report. Republishing the same report (after it
    # was made a draft again) replaces its own column; another report's month
    # is left alone.
    from app.models.sheet_cell import SheetCell
    owner = db.execute(select(SheetCell.report_id).where(
        SheetCell.client_id == client_id, SheetCell.month == month)).scalars().first()
    if owner is not None and owner != report.id:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{month:%B %Y} is already published from another report — make that one a draft first.")

    # This month becomes the client's record: its column is written into
    # every sheet, and keywords or prompts added while building are tracked.
    cells = sheets.publish(db, report, current_user.id)
    flag_modified(report, "snapshot")
    report.status = ReportStatus.published
    report.published_at = datetime.datetime.now(datetime.timezone.utc)
    report.published_by = current_user.id
    db.commit()

    return {"status": "success", "published_at": report.published_at, "month": month.isoformat(),
            "cells": cells, "months": months}



@router.post("/{snapshot_id}/unpublish")
def unpublish_report(client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session = Depends(get_db)):
    """Make a published report a draft again, to change it. Its month stays
    on the sheets as it was until the report is published again, which then
    replaces that month's column with the changed figures."""
    report = _load_draft(client_id, snapshot_id, db, lock=True)
    if report.status != ReportStatus.published:
        raise HTTPException(status.HTTP_409_CONFLICT, "This report is already a draft.")
    report.status = ReportStatus.draft
    report.published_at = None
    report.published_by = None
    db.commit()
    return {"status": "draft"}


class SectionSelection(BaseModel):
    sections: dict[str, bool] | None = None
    items: dict[str, bool] | None = None


class ItemEdits(BaseModel):
    edits: dict[str, Any]


class SectionSuggestRequest(BaseModel):
    instruction: str


class CopyUpdate(BaseModel):
    brand_line: str | None = None
    eyebrows: dict[str, str] | None = None
    titles: dict[str, str] | None = None
    subtitles: dict[str, str] | None = None
    # Every other fixed string the report prints, by its registry id.
    texts: dict[str, str] | None = None


class GenerateRequest(BaseModel):
    # How many 30-day cycles the report covers, ending with the current one.
    months: int = 1


class PeriodChange(BaseModel):
    months: int


class NarrationUpdate(BaseModel):
    narration: dict[str, str]


class PlanItem(BaseModel):
    title: str = ""
    detail: str = ""


class PlanUpdate(BaseModel):
    """What the agency will do next, in two lanes: this coming month, and after.

    Kept on the snapshot rather than the report row so it travels with the
    period the plan was written for, the way the headings and commentary do.
    """
    now: list[PlanItem] | None = None
    next: list[PlanItem] | None = None
    lede: str | None = None


def _load_draft(client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session, lock: bool = False) -> ReportSnapshot:
    """The report; with `lock`, held until this request commits, so two people
    saving at the same moment are applied one after the other instead of the
    second overwriting the first."""
    stmt = select(ReportSnapshot).where(ReportSnapshot.client_id == client_id, ReportSnapshot.id == snapshot_id)
    if lock:
        stmt = stmt.with_for_update()
    report = db.execute(stmt).scalar_one_or_none()
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
    return report


@router.get("/trends")
def get_trends(client_id: uuid.UUID, db: Session = Depends(get_db)):
    """Month by month headline figures, for the overview sparklines — only
    published months, which are the client's final figures."""
    from app.models.sheet_cell import SheetCell
    wanted = {"gsc": ["clicks", "impressions"], "ga4": ["sessions", "users"], "gbp": ["calls", "website_clicks"]}
    series: dict[str, dict[str, list]] = {p: {k: [] for k in ks} for p, ks in wanted.items()}
    for sheet, key, month, value in db.execute(
        select(SheetCell.sheet, SheetCell.row_key, SheetCell.month, SheetCell.value)
        .where(SheetCell.client_id == client_id, SheetCell.sheet.in_(list(wanted)))
        .order_by(SheetCell.month)
    ).all():
        if key in series[sheet]:
            series[sheet][key].append({"d": month.isoformat(), "v": float(value or 0)})
    months = sorted({p["d"] for s_ in series.values() for pts in s_.values() for p in pts})
    return {"from": months[0] if months else None, "to": months[-1] if months else None, "series": series}


@router.get("/periods")
def get_report_periods(client_id: uuid.UUID, snapshot_id: Optional[uuid.UUID] = None, db: Session = Depends(get_db)):
    """What can be generated now: the current cycle, and the cycles before it
    that have data stored and so can be combined into one report. With a
    snapshot_id, the same for that report's own cycle."""
    if snapshot_id:
        report = _load_draft(client_id, snapshot_id, db)
        anchor = {
            "mode": "locked" if report.status == ReportStatus.published else "draft",
            "anchor_end": report.end_date,
            "report_id": str(report.id),
            "months": ((report.snapshot or {}).get("period") or {}).get("months", 1),
            "days_remaining": 0,
        }
    else:
        anchor = periods_svc.anchor_for(db, client_id)
    cycles = periods_svc.timeline(db, client_id, anchor["anchor_end"])
    conns = db.execute(select(Connection).where(Connection.client_id == client_id)).scalars().all()
    connected = {
        p: any(c.provider == ProviderType(p) and c.status == ConnectionStatus.connected for c in conns)
        for p in ("gsc", "ga4")
    }
    return {
        **anchor,
        "anchor_end": anchor["anchor_end"].isoformat(),
        "cycles": cycles,
        "maxMonths": len(cycles),
        "connected": connected,
    }


@router.get("/{snapshot_id}/composer")
def get_composer(client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session = Depends(get_db)):
    """Everything the composer needs: sections, every datum, and current state."""
    report = _load_draft(client_id, snapshot_id, db)
    snapshot = report.snapshot or {}

    # The snapshot stores prompt ids, not their text — resolve them so the
    # composer shows something a person can actually tell apart.
    prompt_labels = {
        str(pid): text_
        for pid, text_ in db.execute(
            select(AiPrompt.id, AiPrompt.prompt_text).where(AiPrompt.client_id == client_id)
        ).all()
    }

    return {
        "sections": composer.SECTIONS,
        "available": composer.section_availability(snapshot),
        "selectedSections": composer.current_sections(snapshot),
        "items": composer.enumerate_items(snapshot, prompt_labels),
        "selectedItems": composer.current_items(snapshot),
        "editable": report.status != ReportStatus.published,
        "copy": composer.current_copy(snapshot),
        "copyHeadings": composer.COPY_HEADINGS,
        # Every other fixed string, grouped by the block it prints under.
        "textFields": report_text.TEXT_FIELDS,
        "brandLineDefault": composer.DEFAULT_BRAND_LINE,
        "hasCover": report.cover_mime is not None,
        "narration": snapshot.get("narration") or {},
        "narrationSource": snapshot.get("narration_source") or {},
        "narrationBlocks": composer.NARRATION_BLOCKS,
        "narrationAvailable": composer.narration_availability(snapshot),
        "plan": snapshot.get("next_month_plan") or {"now": [], "next": [], "lede": ""},
        "planSource": snapshot.get("plan_source"),
        "subtitleAi": snapshot.get("subtitle_ai") or [],
        # The builder draws itself from these: steps in report order, and each
        # slide with what feeds it, its words, and whether it will print.
        "steps": composer.STEPS,
        "slides": _slides_for(db, report, snapshot),
        "kpiCards": _kpi_cards(snapshot),
        "rankOverrides": composer.clean_rank_overrides((snapshot.get("rankings") or {}).get("summary_overrides")),
        "aiSummary": snapshot.get("ai_summary") or {},
        # Worked-out figures, listing every assistant a figure was typed or read in for too.
        "aiSummaryAuto": __import__("app.services.slide_deck", fromlist=["ai_summary"]).ai_summary(
            {**snapshot, "ai_summary": {"engines": {k: {} for k in ((snapshot.get("ai_summary") or {}).get("engines") or {})}}}),
        "period": snapshot.get("period") or _legacy_period(report),
        # The breakdown tables, editable row by row.
        "listSpecs": [
            {**spec, "columns": [{"key": k, "label": l, "type": t} for k, l, t in spec["columns"]]}
            for spec in composer.LIST_SPECS
        ],
        "lists": {spec["path"]: composer.list_rows(snapshot, spec["path"]) for spec in composer.LIST_SPECS},
        "periods": snapshot.get("periods") or [],
        "dataHealth": _data_health(db, client_id, snapshot, report),
    }


def _data_health(db: Session, client_id: uuid.UUID, snapshot: dict, report: ReportSnapshot) -> dict:
    """Whether each connected source's figures can be trusted for this period.

    A broken connection does not stop a report being built — it reads whatever
    is stored, which is what makes manual entry work at all. The danger is the
    quiet case: a connection that has been failing for weeks, a report that
    prints the last figures it ever managed to collect, and nothing on the
    page saying so. This is what the builder warns on before that goes out.
    """
    provenance = snapshot.get("provenance") or {}
    period = snapshot.get("period") or {}
    try:
        window_start = datetime.date.fromisoformat(period.get("start") or report.start_date.isoformat())
    except (TypeError, ValueError):
        window_start = report.start_date

    connections = {
        c.provider.value: c
        for c in db.execute(select(Connection).where(Connection.client_id == client_id)).scalars()
    }

    out: dict[str, dict] = {}
    for provider in ("gsc", "ga4", "gbp"):
        conn = connections.get(provider)
        newest_raw = (provenance.get(provider) or {}).get("newest")
        newest = None
        if newest_raw:
            try:
                newest = datetime.date.fromisoformat(newest_raw)
            except (TypeError, ValueError):
                newest = None

        out[provider] = {
            "connected": bool(conn and conn.status == ConnectionStatus.connected),
            "status": conn.status.value if conn else "not_connected",
            "lastError": (conn.last_error or "") if conn else "",
            "lastSync": conn.last_sync_at.date().isoformat() if conn and conn.last_sync_at else None,
            "newest": newest.isoformat() if newest else None,
            # Figures from before this report's window are not this period's
            # figures, whatever the slide says.
            "stale": bool(newest and newest < window_start),
            "source": (provenance.get(provider) or {}).get("source"),
        }
    return out


def _slides_for(db: Session, report: ReportSnapshot, snapshot: dict) -> list[dict]:
    images = {
        section: count for section, count in db.execute(
            select(ReportImage.section, func.count()).where(ReportImage.report_id == report.id)
            .group_by(ReportImage.section)
        ).all()
    }
    status_ = composer.slide_status(snapshot, images)
    return [
        {**{k: v for k, v in slide.items() if k != "texts"},
         "texts": composer.slide_texts(slide), **status_.get(slide["key"], {})}
        for slide in composer.SLIDES
    ]


def _kpi_cards(snapshot: dict) -> list[dict]:
    """The cards Performance Highlight can print for this report — its own
    list, with the real values — and whether each is switched on."""
    from app.services import slide_deck
    sections = composer.current_sections(snapshot)
    chosen = composer.current_items(snapshot)
    t = report_text.resolver(snapshot.get("copy"))
    cards = slide_deck.scorecard({**snapshot, "hidden_cards": []}, sections,
                                 lambda i: chosen.get(i, True) is not False, False, t)
    hidden = set(snapshot.get("hidden_cards") or [])
    return [{"id": c["card"], "name": c["name"], "value": c["value"], "shown": c["card"] not in hidden} for c in cards]


class CardToggle(BaseModel):
    id: str
    shown: bool


@router.put("/{snapshot_id}/cards")
def set_kpi_card(client_id: uuid.UUID, snapshot_id: uuid.UUID, data: CardToggle, db: Session = Depends(get_db)):
    """Show or hide one Performance Highlight card."""
    report = _load_editable(client_id, snapshot_id, db)
    snapshot = dict(report.snapshot or {})
    hidden = set(snapshot.get("hidden_cards") or [])
    (hidden.discard if data.shown else hidden.add)(data.id)
    snapshot["hidden_cards"] = sorted(hidden)
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return {"kpiCards": _kpi_cards(snapshot)}


class SlideToggle(BaseModel):
    key: str
    shown: bool


@router.put("/{snapshot_id}/slides")
def set_slide_shown(client_id: uuid.UUID, snapshot_id: uuid.UUID, data: SlideToggle, db: Session = Depends(get_db)):
    """Show or hide one slide. Showing a slide whose data section was switched
    off switches that section back on, so the switch does what it says."""
    slide = next((x for x in composer.SLIDES if x["key"] == data.key), None)
    if not slide:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown slide.")
    report = _load_editable(client_id, snapshot_id, db)
    snapshot = dict(report.snapshot or {})
    hidden = set(snapshot.get("hidden_slides") or [])
    if data.shown:
        hidden.discard(data.key)
        section = slide.get("section")
        if section and composer.section_availability(snapshot).get(section):
            chosen = dict(composer.current_sections(snapshot))
            chosen[section] = True
            snapshot["included_sections"] = chosen
    else:
        hidden.add(data.key)
    snapshot["hidden_slides"] = sorted(hidden)
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return {"slides": _slides_for(db, report, snapshot), "selectedSections": composer.current_sections(snapshot)}


@router.put("/{snapshot_id}/composer")
def set_composer(
    client_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    data: SectionSelection,
    db: Session = Depends(get_db),
):
    """Save which sections and which individual figures the report shows."""
    report = _load_draft(client_id, snapshot_id, db, lock=True)
    if report.status == ReportStatus.published:
        raise HTTPException(status.HTTP_409_CONFLICT, "Published reports cannot be edited.")

    snapshot = dict(report.snapshot or {})

    if data.sections is not None:
        # Sections print with or without data; a person's switch is the only choice.
        stored = dict(snapshot.get("included_sections") or {})
        for k in composer.SECTION_KEYS:
            if k in data.sections:
                stored[k] = bool(data.sections[k])
        snapshot["included_sections"] = stored

    if data.items is not None:
        current_items = composer.current_items(snapshot)
        snapshot["included_items"] = {
            i: bool(data.items.get(i, current_items[i])) for i in current_items
        }

    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()

    return {
        "selectedSections": composer.current_sections(snapshot),
        "selectedItems": composer.current_items(snapshot),
    }


@router.put("/{snapshot_id}/values")
def set_composer_values(
    client_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    data: ItemEdits,
    db: Session = Depends(get_db),
):
    """Overwrite individual figures on a draft report.

    Period-on-period deltas for headline figures are re-derived from the
    previous period implied by the existing delta, so an edited number can never
    sit beside a percentage that contradicts it.
    """
    report = _load_draft(client_id, snapshot_id, db, lock=True)
    if report.status == ReportStatus.published:
        raise HTTPException(status.HTTP_409_CONFLICT, "Published reports cannot be edited.")

    snapshot = dict(report.snapshot or {})
    deltas = {k: dict(v) for k, v in (snapshot.get("kpi_deltas") or {}).items() if isinstance(v, dict)}
    previous_values = {k: dict(v) for k, v in (snapshot.get("previous_values") or {}).items() if isinstance(v, dict)}
    comparable = composer.comparable_keys()
    applied, rejected = [], []

    def number(item_id: str, raw) -> float:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{item_id} must be a number.")
        if value < 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"{item_id} cannot be negative.")
        return value

    def settle(provider: str, key: str, previous: Optional[float]) -> None:
        """Keep the change equal to this period minus the previous one."""
        if previous is None:
            return
        current = float((snapshot.get(provider) or {}).get(key) or 0)
        previous_values.setdefault(provider, {})[key] = previous
        deltas.setdefault(provider, {})[key] = current - previous

    # Where each keyword started. Kept in the draft; publishing saves it on
    # the keyword, so every later report starts from the same place.
    for item_id, raw in data.edits.items():
        if not item_id.startswith("init:rankings.kw."):
            continue
        ident = item_id[len("init:rankings.kw."):]
        if composer.write_initial_position(snapshot, ident, number(item_id, raw)):
            applied.append(item_id)
        else:
            rejected.append(item_id)

    # Last period's figures first, so an edit to both lands on the new pair.
    for item_id, raw in data.edits.items():
        if not item_id.startswith("prev:"):
            continue
        if item_id.startswith("prev:ga4.lead."):
            if composer.write_previous_lead(snapshot, item_id[len("prev:ga4.lead."):], number(item_id, raw)):
                applied.append(item_id)
            else:
                rejected.append(item_id)
            continue
        if item_id.startswith("prev:rankings.kw."):
            if composer.write_previous_position(snapshot, item_id[len("prev:rankings.kw."):], number(item_id, raw)):
                applied.append(item_id)
            else:
                rejected.append(item_id)
            continue
        provider, _, key = item_id[5:].partition(".")
        if key not in comparable.get(provider, []):
            rejected.append(item_id)
            continue
        snapshot["previous_values"] = previous_values
        settle(provider, key, number(item_id, raw))
        applied.append(item_id)

    for item_id, raw in data.edits.items():
        if item_id.startswith(("prev:", "init:")):
            continue
        provider, _, key = item_id.partition(".")
        pairs = key in comparable.get(provider, [])
        if pairs:
            number(item_id, raw)
            snapshot["previous_values"] = previous_values
            snapshot["kpi_deltas"] = deltas
            before = composer.previous_value(snapshot, provider, key)

        if composer.write_edit(snapshot, item_id, raw):
            applied.append(item_id)
            if pairs:
                settle(provider, key, before)
        else:
            rejected.append(item_id)

    snapshot["previous_values"] = previous_values
    # Keyword positions changed: the ranking summary follows them.
    if any(i.startswith(("rankings.kw.", "prev:rankings.kw.")) for i in applied):
        rankings = dict(snapshot.get("rankings") or {})
        rankings["summary"] = composer.ranking_summary(rankings.get("keywords") or [], rankings.get("summary_overrides"))
        snapshot["rankings"] = rankings
    # Once a previous figure is known, the report says what it compares with.
    if any(v for block in previous_values.values() for v in block.values()):
        period = dict(snapshot.get("period") or {})
        compare = dict(period.get("compare") or {})
        if not compare.get("hasData"):
            compare["hasData"] = True
            period["compare"] = compare
            snapshot["period"] = period

    snapshot["kpi_deltas"] = deltas
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()

    return {"applied": applied, "rejected": rejected, "items": composer.enumerate_items(snapshot),
            "available": composer.section_availability(snapshot),
            "selectedSections": composer.current_sections(snapshot),
            "kpiCards": _kpi_cards(snapshot), "slides": _slides_for(db, report, snapshot)}


@router.post("/{snapshot_id}/composer/suggest")
def suggest_composer(
    client_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    data: SectionSuggestRequest,
    db: Session = Depends(get_db),
):
    """Turn a plain-language instruction into a selection.

    Nothing is saved here — the result is handed back for the user to confirm.
    """
    report = _load_draft(client_id, snapshot_id, db, lock=True)
    snapshot = report.snapshot or {}

    try:
        return suggest_report_sections(
            instruction=data.instruction,
            sections=composer.current_sections(snapshot),
            items=composer.enumerate_items(snapshot),
            item_state=composer.current_items(snapshot),
            available=composer.section_availability(snapshot),
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))


COVER_MAX_BYTES = settings.MAX_IMAGE_MB * 1024 * 1024


def _load_editable(client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session) -> ReportSnapshot:
    report = _load_draft(client_id, snapshot_id, db, lock=True)
    if report.status == ReportStatus.published:
        raise HTTPException(status.HTTP_409_CONFLICT, "Published reports cannot be edited.")
    return report


def _sniff_image(data: bytes) -> Optional[str]:
    """The image type from the file's own bytes — the browser's claim is not trusted."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


class RankSummaryEdit(BaseModel):
    bands: dict[str, dict[str, Optional[float]]] = {}
    moves: dict[str, Optional[float]] = {}


@router.put("/{snapshot_id}/rank-summary")
def set_rank_summary(client_id: uuid.UUID, snapshot_id: uuid.UUID, data: RankSummaryEdit, db: Session = Depends(get_db)):
    """Figures typed over the ranking summary. A band or count left blank goes
    back to being worked out from the keywords."""
    report = _load_editable(client_id, snapshot_id, db)
    snapshot = dict(report.snapshot or {})
    rankings = dict(snapshot.get("rankings") or {})
    overrides = composer.clean_rank_overrides({"bands": data.bands, "moves": data.moves})
    rankings["summary_overrides"] = overrides
    rankings["summary"] = composer.ranking_summary(rankings.get("keywords") or [], overrides)
    snapshot["rankings"] = rankings
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return {"overrides": overrides, "summary": rankings["summary"]}


class NewKeyword(BaseModel):
    term: str
    position: Optional[int] = None
    previous: Optional[int] = None
    initial: Optional[int] = None
    search_volume: Optional[int] = None


@router.post("/{snapshot_id}/keywords")
def add_report_keyword(client_id: uuid.UUID, snapshot_id: uuid.UUID, data: NewKeyword, db: Session = Depends(get_db)):
    """Add a keyword from the builder. It lives in this draft; publishing the
    report makes it one of the client's tracked keywords."""
    report = _load_editable(client_id, snapshot_id, db)
    term = " ".join(data.term.split())[:200]
    if not term:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Type the keyword.")
    for n in (data.position, data.previous, data.initial, data.search_volume):
        if n is not None and n < 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Positions cannot be negative.")

    snapshot = dict(report.snapshot or {})
    rankings = dict(snapshot.get("rankings") or {})
    keywords = list(rankings.get("keywords") or [])
    if any(str(k.get("term") or "").strip().lower() == term.lower() for k in keywords):
        raise HTTPException(status.HTTP_409_CONFLICT, f"“{term}” is already in this report.")

    # A keyword the client already tracks keeps its id; a new one is named
    # until publishing gives it one.
    known = db.execute(
        select(Keyword).where(Keyword.client_id == client_id, func.lower(Keyword.term) == term.lower())
    ).scalars().first()
    initial = data.initial or (known.initial_rank if known else None)
    keywords.append({
        "keyword_id": str(known.id) if known else f"new-{uuid.uuid4().hex[:12]}",
        "term": term,
        "position": data.position or None,
        "previous_position": data.previous or None,
        "initial_rank": initial,
        "search_volume": data.search_volume if data.search_volume is not None else (known.search_volume if known else None),
        "change": (initial - data.position) if initial and data.position else None,
        "history": {},
    })
    rankings["keywords"] = keywords
    rankings["summary"] = composer.ranking_summary(keywords, rankings.get("summary_overrides"))
    snapshot["rankings"] = rankings
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return get_composer(client_id, snapshot_id, db)


class NewPrompt(BaseModel):
    prompt: str
    results: dict[str, Optional[bool]] = {}


@router.post("/{snapshot_id}/ai-prompts")
def add_report_prompt(client_id: uuid.UUID, snapshot_id: uuid.UUID, data: NewPrompt, db: Session = Depends(get_db)):
    """Add an AI visibility prompt from the builder, with whether each
    assistant named the brand. It lives in this draft; publishing the report
    makes it one of the client's tracked prompts."""
    report = _load_editable(client_id, snapshot_id, db)
    text_ = " ".join(data.prompt.split())[:300]
    if not text_:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Type the prompt.")
    results = {}
    for name, seen in data.results.items():
        try:
            results[AiPlatform(name).value] = seen
        except ValueError:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown assistant: {name}.")
    if not results:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Mark at least one assistant.")

    snapshot = dict(report.snapshot or {})
    rows = list(snapshot.get("ai_visibility") or [])
    if any((r.get("prompt") or "").strip().lower() == text_.lower() for r in rows):
        raise HTTPException(status.HTTP_409_CONFLICT, "That prompt is already in this report.")

    known = db.execute(
        select(AiPrompt).where(AiPrompt.client_id == client_id, func.lower(AiPrompt.prompt_text) == text_.lower())
    ).scalars().first()
    ident = str(known.id) if known else f"new-{uuid.uuid4().hex[:12]}"
    # Answers given here are this month's, so the whole grid now stands.
    rows = [{k: v for k, v in r.items() if k != "unchecked"} for r in rows]
    for platform, seen in results.items():
        rows.append({"prompt_id": ident, "platform": platform, "mentioned": bool(seen),
                     "cited_pages": None, "prompt": text_})

    snapshot["ai_visibility"] = rows
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return get_composer(client_id, snapshot_id, db)


class AiSummaryEdit(BaseModel):
    score: Optional[float] = None
    mentions: Optional[float] = None
    cited: Optional[float] = None
    engines: dict[str, dict[str, Optional[float]]] = {}


@router.post("/{snapshot_id}/ai-summary/read")
async def read_ai_summary(client_id: uuid.UUID, snapshot_id: uuid.UUID, file: UploadFile = File(...),
                          db: Session = Depends(get_db)):
    """Read the AI results figures off a screenshot of an AI-visibility tool
    and fill them in. Each one stays editable; the screenshot is kept with the
    report so the figures can be checked against it."""
    from app.services.openai_service import read_ai_summary_screenshot
    from app.services.slide_deck import ai_summary
    report = _load_editable(client_id, snapshot_id, db)
    data = await file.read(COVER_MAX_BYTES + 1)
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The file is empty.")
    if len(data) > COVER_MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"The screenshot must be {settings.MAX_IMAGE_MB} MB or smaller.")
    mime = _sniff_image(data)
    if not mime:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Use a PNG, JPEG or WebP screenshot.")
    try:
        read = read_ai_summary_screenshot(data, mime)
    except Exception as e:
        logger.warning("AI summary screenshot could not be read: %s", e)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The screenshot could not be read right now — try again, or type the figures.")
    if not read:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No AI visibility figures were found in that screenshot.")

    img = _find_image(db, report.id, "ai_summary", 0)
    if img is None:
        img = ReportImage(report_id=report.id, section="ai_summary", slot=0, mime=mime, data=data)
        db.add(img)
    else:
        img.mime, img.data = mime, data
    snapshot = dict(report.snapshot or {})
    typed = dict(snapshot.get("ai_summary") or {})
    for k in ("score", "mentions", "cited"):
        if read.get(k) is not None:
            typed[k] = read[k]
    if read.get("engines"):
        typed["engines"] = {**(typed.get("engines") or {}), **read["engines"]}
    snapshot["ai_summary"] = typed
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return {"read": read, "typed": typed, "shown": ai_summary(snapshot)}


@router.put("/{snapshot_id}/ai-summary")
def set_ai_summary(client_id: uuid.UUID, snapshot_id: uuid.UUID, data: AiSummaryEdit, db: Session = Depends(get_db)):
    """AI Visibility score, total mentions, total cited pages and each
    assistant's figures. A blank figure goes back to being worked out."""
    from app.services.slide_deck import AI_SUMMARY_ENGINES, ai_summary
    report = _load_editable(client_id, snapshot_id, db)
    snapshot = dict(report.snapshot or {})

    def num(v):
        if v is None:
            return None
        if v < 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Figures cannot be negative.")
        return int(round(v))

    from app.services.slide_deck import ENGINE_NAME
    known = {k for k, _ in AI_SUMMARY_ENGINES} | set(ENGINE_NAME)
    engines = {}
    for key, cell in data.engines.items():
        if key not in known:
            continue
        kept = {f: num(cell.get(f)) for f in ("mentions", "cited") if cell.get(f) is not None}
        if kept:
            engines[key] = kept
    typed = {k: num(v) for k, v in (("score", data.score), ("mentions", data.mentions), ("cited", data.cited)) if v is not None}
    if typed.get("score") is not None and typed["score"] > 100:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "AI Visibility is a score out of 100.")
    if engines:
        typed["engines"] = engines
    snapshot["ai_summary"] = typed
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return {"typed": typed, "shown": ai_summary(snapshot)}


class ListEdit(BaseModel):
    path: str
    rows: list[dict[str, Any]]


@router.put("/{snapshot_id}/lists")
def set_report_list(client_id: uuid.UUID, snapshot_id: uuid.UUID, data: ListEdit, db: Session = Depends(get_db)):
    """Replace one breakdown table (top pages, countries, channels…) on a draft."""
    report = _load_editable(client_id, snapshot_id, db)
    snapshot = dict(report.snapshot or {})
    if not composer.write_list(snapshot, data.path, data.rows):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "That table can't be edited.")
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return {"path": data.path, "rows": composer.list_rows(snapshot, data.path)}


@router.put("/{snapshot_id}/copy")
def set_report_copy(client_id: uuid.UUID, snapshot_id: uuid.UUID, data: CopyUpdate, db: Session = Depends(get_db)):
    """Headings, subtitles and the cover's brand line. A blank value restores the default."""
    report = _load_editable(client_id, snapshot_id, db)
    snapshot = dict(report.snapshot or {})
    before = dict(((snapshot.get("copy") or {}).get("subtitles")) or {})
    snapshot["copy"] = composer.merge_copy(
        snapshot, data.brand_line, data.titles, data.subtitles, data.eyebrows, data.texts
    )
    after = dict(((snapshot.get("copy") or {}).get("subtitles")) or {})
    changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    if changed:
        snapshot["subtitle_ai"] = sorted(set(snapshot.get("subtitle_ai") or []) - changed)
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return {"copy": composer.current_copy(snapshot), "subtitleAi": snapshot.get("subtitle_ai") or []}


def draft_plan(client_name: str, snapshot: dict, force: bool = False) -> bool:
    """Fill the Next Plan of Action with an AI draft, in place. A plan someone
    has edited is never replaced unless `force` (the builder's Rewrite button).
    Never blocks: if the AI is unavailable the plan stays as it was."""
    stored = snapshot.get("next_month_plan") if isinstance(snapshot.get("next_month_plan"), dict) else {}
    if (stored.get("now") or stored.get("next")) and not force:
        return False
    try:
        plan = generate_next_plan(client_name, (snapshot.get("period") or {}).get("label", ""),
                                  composer.apply_selection(snapshot))
    except Exception:
        logger.exception("Next plan of action could not be written.")
        return False
    if not plan:
        return False
    snapshot["next_month_plan"] = plan
    snapshot["plan_source"] = "ai"
    return True


def autofill_text(client_name: str, snapshot: dict) -> dict[str, int]:
    """Fill every empty text box the builder shows with an AI draft, in place:
    each slide's summary, each slide's subtitle, and the next plan of action.
    Nothing a person typed is replaced. A subtitle is drafted once — if it is
    then cleared on purpose, it stays clear. Never blocks: if the AI is
    unavailable the boxes simply stay empty."""
    filled = {"summaries": 0, "subtitles": 0, "plan": 0}
    available = composer.narration_availability(snapshot)

    # Summaries: every block with figures and no text yet.
    narration = dict(snapshot.get("narration") or {})
    source = dict(snapshot.get("narration_source") or {})
    empty = [k for k in composer.NARRATION_KEYS if available.get(k) and not str(narration.get(k) or "").strip()]
    if empty:
        written = _write_narration(client_name, snapshot, empty)
        for key, text_ in written.items():
            narration[key], source[key] = text_, composer.NARRATION_AI
        snapshot["narration"], snapshot["narration_source"] = narration, source
        filled["summaries"] = len(written)

    # Subtitles: blocks with figures, no subtitle, never drafted before.
    copy_ = dict(snapshot.get("copy") or {})
    subtitles = dict(copy_.get("subtitles") or {})
    drafted = set(snapshot.get("subtitles_drafted") or [])
    todo = [k for k in composer.NARRATION_KEYS
            if available.get(k) and not str(subtitles.get(k) or "").strip() and k not in drafted]
    if todo:
        try:
            lines = generate_slide_subtitles(client_name, (snapshot.get("period") or {}).get("label", ""),
                                             composer.apply_selection(snapshot), todo)
        except Exception:
            logger.exception("Slide subtitles could not be written.")
            lines = {}
        if lines:
            subtitles.update(lines)
            copy_["subtitles"] = subtitles
            snapshot["copy"] = copy_
            snapshot["subtitles_drafted"] = sorted(drafted | set(lines))
            snapshot["subtitle_ai"] = sorted(set(snapshot.get("subtitle_ai") or []) | set(lines))
            filled["subtitles"] = len(lines)

    # The closing plan, when it is empty.
    if draft_plan(client_name, snapshot):
        filled["plan"] = 1
    return filled


@router.post("/{snapshot_id}/ai-text/refresh")
def refresh_ai_text(client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session = Depends(get_db)):
    """Rewrite everything the AI wrote — summaries, subtitles, the plan — from
    the figures as they are now. Text a person typed or edited is left alone."""
    report = _load_editable(client_id, snapshot_id, db)
    client = db.get(Client, client_id)
    name = client.name if client else ""
    snapshot = dict(report.snapshot or {})
    draft_narration(name, snapshot)
    ai_subs = set(snapshot.get("subtitle_ai") or [])
    if ai_subs:
        copy_ = dict(snapshot.get("copy") or {})
        copy_["subtitles"] = {k: v for k, v in (copy_.get("subtitles") or {}).items() if k not in ai_subs}
        snapshot["copy"] = copy_
        snapshot["subtitles_drafted"] = [k for k in (snapshot.get("subtitles_drafted") or []) if k not in ai_subs]
        snapshot["subtitle_ai"] = []
    autofill_text(name, snapshot)
    if snapshot.get("plan_source") == "ai" or not (snapshot.get("next_month_plan") or {}).get("now"):
        draft_plan(name, snapshot, force=True)
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return get_composer(client_id, snapshot_id, db)


@router.post("/{snapshot_id}/plan/draft")
def draft_report_plan(client_id: uuid.UUID, snapshot_id: uuid.UUID, force: bool = False, db: Session = Depends(get_db)):
    """Write the Next Plan of Action with AI. Without `force`, only an empty
    plan is filled — the builder calls this when the step is first opened."""
    report = _load_editable(client_id, snapshot_id, db)
    snapshot = dict(report.snapshot or {})
    client = db.get(Client, client_id)
    if not draft_plan(client.name if client else "", snapshot, force=force):
        stored = snapshot.get("next_month_plan")
        if force and not (isinstance(stored, dict) and (stored.get("now") or stored.get("next"))):
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The plan could not be written right now — try again.")
        return {"plan": stored or {"now": [], "next": [], "lede": ""}, "source": snapshot.get("plan_source"), "written": False}
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return {"plan": snapshot["next_month_plan"], "source": "ai", "written": True}


@router.put("/{snapshot_id}/plan")
def set_report_plan(client_id: uuid.UUID, snapshot_id: uuid.UUID, data: PlanUpdate, db: Session = Depends(get_db)):
    """The Next Plan of Action slide. Rows without a title are dropped."""
    report = _load_editable(client_id, snapshot_id, db)
    snapshot = dict(report.snapshot or {})
    stored = snapshot.get("next_month_plan")
    plan = dict(stored) if isinstance(stored, dict) else {}

    def lane(rows: list[PlanItem]) -> list[dict]:
        return [
            {"title": r.title.strip()[:90], "detail": r.detail.strip()[:200]}
            for r in rows if r.title.strip()
        ][:3]

    if data.now is not None:
        plan["now"] = lane(data.now)
    if data.next is not None:
        plan["next"] = lane(data.next)
    if data.lede is not None:
        plan["lede"] = data.lede.strip()[:240]

    if plan != stored:
        snapshot["plan_source"] = "edited"
    snapshot["next_month_plan"] = plan
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return {"plan": plan, "source": snapshot.get("plan_source")}


@router.get("/{snapshot_id}/cover")
def get_report_cover(client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session = Depends(get_db)):
    report = _load_draft(client_id, snapshot_id, db, lock=True)
    if not report.cover_mime or not report.cover_image:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No cover screenshot.")
    return Response(content=report.cover_image, media_type=report.cover_mime, headers={"Cache-Control": "no-store"})


@router.put("/{snapshot_id}/cover")
async def set_report_cover(
    client_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """The website homepage screenshot shown on the cover. PNG, JPEG or WebP, up to 5 MB."""
    report = _load_editable(client_id, snapshot_id, db)
    data = await file.read(COVER_MAX_BYTES + 1)
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The file is empty.")
    if len(data) > COVER_MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "The cover screenshot must be 5 MB or smaller.")
    mime = _sniff_image(data)
    if not mime:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The cover screenshot must be a PNG, JPEG or WebP image.")
    report.cover_image = data
    report.cover_mime = mime
    db.commit()
    return {"hasCover": True}


@router.delete("/{snapshot_id}/cover")
def delete_report_cover(client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session = Depends(get_db)):
    report = _load_editable(client_id, snapshot_id, db)
    report.cover_image = None
    report.cover_mime = None
    db.commit()
    return {"hasCover": False}


# Report slides that carry their own screenshots, and how many each holds.
# ai_summary: the AI-visibility tool screenshot its figures were read from (not printed).
IMAGE_SLOTS = {"gbp": 5, "ai": 6, "ai_summary": 1}


class ImageCaption(BaseModel):
    caption: str = ""


def _image_slot(section: str, slot: int) -> None:
    if section not in IMAGE_SLOTS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This slide has no screenshots.")
    if not 0 <= slot < IMAGE_SLOTS[section]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Slots run from 1 to {IMAGE_SLOTS[section]}.")


def _find_image(db: Session, report_id: uuid.UUID, section: str, slot: int) -> Optional[ReportImage]:
    return db.execute(select(ReportImage).where(
        ReportImage.report_id == report_id, ReportImage.section == section, ReportImage.slot == slot,
    )).scalar_one_or_none()


@router.get("/{snapshot_id}/images/{section}")
def list_report_images(client_id: uuid.UUID, snapshot_id: uuid.UUID, section: str, db: Session = Depends(get_db)):
    """Every slot of a slide's screenshots, filled or not."""
    _image_slot(section, 0)
    report = _load_draft(client_id, snapshot_id, db)
    found = {
        img.slot: img for img in db.execute(
            select(ReportImage).where(ReportImage.report_id == report.id, ReportImage.section == section)
        ).scalars()
    }
    return [
        {"slot": i, "hasImage": i in found, "caption": (found[i].caption or "") if i in found else ""}
        for i in range(IMAGE_SLOTS[section])
    ]


@router.get("/{snapshot_id}/images/{section}/{slot}")
def get_report_image(client_id: uuid.UUID, snapshot_id: uuid.UUID, section: str, slot: int,
                     db: Session = Depends(get_db)):
    _image_slot(section, slot)
    report = _load_draft(client_id, snapshot_id, db)
    img = _find_image(db, report.id, section, slot)
    if not img:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No screenshot in this slot.")
    return Response(content=img.data, media_type=img.mime, headers={"Cache-Control": "no-store"})


@router.put("/{snapshot_id}/images/{section}/{slot}")
async def set_report_image(
    client_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    section: str,
    slot: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """A screenshot for one slot of a slide. PNG, JPEG or WebP, up to 5 MB.
    Replacing an image keeps the slot's caption."""
    _image_slot(section, slot)
    report = _load_editable(client_id, snapshot_id, db)
    data = await file.read(COVER_MAX_BYTES + 1)
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "The file is empty.")
    if len(data) > COVER_MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Each screenshot must be 5 MB or smaller.")
    mime = _sniff_image(data)
    if not mime:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Screenshots must be PNG, JPEG or WebP images.")
    img = _find_image(db, report.id, section, slot)
    if img is None:
        img = ReportImage(report_id=report.id, section=section, slot=slot)
        db.add(img)
    img.data = data
    img.mime = mime
    db.commit()
    return {"slot": slot, "hasImage": True, "caption": img.caption or ""}


@router.patch("/{snapshot_id}/images/{section}/{slot}")
def set_report_image_caption(client_id: uuid.UUID, snapshot_id: uuid.UUID, section: str, slot: int,
                             body: ImageCaption, db: Session = Depends(get_db)):
    _image_slot(section, slot)
    report = _load_editable(client_id, snapshot_id, db)
    img = _find_image(db, report.id, section, slot)
    if not img:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Add a screenshot before its caption.")
    img.caption = body.caption.strip()[:160] or None
    db.commit()
    return {"slot": slot, "hasImage": True, "caption": img.caption or ""}


@router.delete("/{snapshot_id}/images/{section}/{slot}")
def delete_report_image(client_id: uuid.UUID, snapshot_id: uuid.UUID, section: str, slot: int,
                        db: Session = Depends(get_db)):
    _image_slot(section, slot)
    report = _load_editable(client_id, snapshot_id, db)
    img = _find_image(db, report.id, section, slot)
    if img:
        db.delete(img)
        db.commit()
    return {"slot": slot, "hasImage": False, "caption": ""}


@router.post("/{snapshot_id}/fetch/{provider}")
def refetch_provider(client_id: uuid.UUID, snapshot_id: uuid.UUID, provider: str, db: Session = Depends(get_db)):
    """Pull fresh Search Console, Analytics or Business Profile figures into a
    draft, for its own window and the one it is compared with.

    Only that provider's block and its comparison change. Nothing is stored
    anywhere but this draft.
    """
    from app.tasks.reports import pull_for_report
    if provider not in ("gsc", "ga4", "gbp"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Only Search Console, Analytics and Business Profile can be fetched.")
    report = _load_editable(client_id, snapshot_id, db)

    name = {"gsc": "Search Console", "ga4": "Google Analytics", "gbp": "Business Profile"}[provider]
    conn = db.execute(
        select(Connection).where(Connection.client_id == client_id, Connection.provider == ProviderType(provider))
    ).scalars().first()
    if not conn or conn.status != ConnectionStatus.connected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"{name} is not connected for this client.")

    months = ((report.snapshot or {}).get("period") or {}).get("months") or 1
    rows, live = pull_for_report(db, client_id, report.end_date, months, providers=(provider,))
    if not rows:
        db.refresh(conn)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Could not fetch from {name}: {conn.last_error or 'no data returned'}")

    # The pull committed (the connection's health), which released the row;
    # take it again so an edit made meanwhile is built on, not overwritten.
    report = _load_draft(client_id, snapshot_id, db, lock=True)
    snapshot = dict(report.snapshot or {})
    current = dict(_live_of(snapshot))
    current.pop(provider, None)
    current.update(live)
    with periods_svc.pulled(rows):
        fresh = periods_svc.build_report_data(db, client_id, report.end_date, months, live=current,
                                              with_page_images=provider == "gsc")
    snapshot = periods_svc.merge_section(snapshot, fresh, provider)
    snapshot["live"] = {**(snapshot.get("live") or {}), **{k: v for k, v in (fresh.get("live") or {}).items() if k == provider}}
    provenance = dict(snapshot.get("provenance") or {})
    provenance[provider] = (fresh.get("provenance") or {}).get(provider)
    snapshot["provenance"] = provenance

    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return get_composer(client_id, snapshot_id, db)


def _legacy_period(report: ReportSnapshot) -> dict:
    """Period details for a report made before reports could span months."""
    label = report.end_date.strftime("%B %Y")
    return {
        "months": 1,
        "start": report.start_date.isoformat(),
        "end": report.end_date.isoformat(),
        "labels": [label],
        "label": label,
        "range": periods_svc.short_range(report.start_date, report.end_date),
        "compare": {"hasData": bool((report.snapshot or {}).get("kpi_deltas"))},
    }


def _live_of(snapshot: dict) -> dict:
    """The current month's blocks as the draft has them. A one-month draft's
    own blocks are that month, with every edit made to them; a combined one
    keeps the current month apart under `live`."""
    if ((snapshot.get("period") or {}).get("months") or 1) == 1:
        return {p: dict(snapshot[p]) for p in ("gsc", "ga4", "gbp") if isinstance(snapshot.get(p), dict) and snapshot.get(p)}
    live = snapshot.get("live")
    return dict(live) if isinstance(live, dict) else {}


def _write_narration(client_name: str, snapshot: dict, sections: Optional[list[str]] = None) -> dict:
    """Section commentary for every section that has something to say.
    Never blocks a report: if the AI is unavailable the sections stay empty."""
    available = composer.narration_availability(snapshot)
    wanted = [s for s in (sections or composer.NARRATION_KEYS) if available.get(s)]
    if not wanted:
        return {}
    try:
        return generate_section_summaries(
            client_name, (snapshot.get("period") or {}).get("label", ""),
            composer.apply_selection(snapshot), wanted, composer.current_items(snapshot),
        )
    except Exception:
        logger.exception("Section commentary could not be written.")
        return {}


def clear_ai_text(snapshot: dict) -> None:
    """Remove every summary, subtitle and plan the AI wrote, in place."""
    narration = dict(snapshot.get("narration") or {})
    source = dict(snapshot.get("narration_source") or {})
    for key, by in list(source.items()):
        if by == composer.NARRATION_AI:
            narration.pop(key, None)
            source.pop(key, None)
    snapshot["narration"], snapshot["narration_source"] = narration, source
    ai_subs = set(snapshot.get("subtitle_ai") or [])
    if ai_subs:
        copy_ = dict(snapshot.get("copy") or {})
        copy_["subtitles"] = {k: v for k, v in (copy_.get("subtitles") or {}).items() if k not in ai_subs}
        snapshot["copy"] = copy_
        snapshot["subtitles_drafted"] = [k for k in (snapshot.get("subtitles_drafted") or []) if k not in ai_subs]
        snapshot["subtitle_ai"] = []
    if snapshot.get("plan_source") == "ai":
        snapshot["next_month_plan"] = {"now": [], "next": [], "lede": ""}
        snapshot["plan_source"] = None


def draft_narration(client_name: str, snapshot: dict) -> None:
    """Draft the commentary this report is missing, in place.

    Only ever fills or refreshes AI-written text. A paragraph someone typed is
    left exactly as they left it, however much the figures around it moved.
    """
    existing = dict(snapshot.get("narration") or {})
    source = dict(snapshot.get("narration_source") or {})
    keep_written = {k for k, v in source.items() if v == composer.NARRATION_EDITED and existing.get(k)}

    wanted = [k for k in composer.NARRATION_KEYS if k not in keep_written]
    written = _write_narration(client_name, snapshot, wanted)
    if not written:
        snapshot["narration"], snapshot["narration_source"] = existing, source
        return

    for key, text_ in written.items():
        existing[key] = text_
        source[key] = composer.NARRATION_AI
    snapshot["narration"] = existing
    snapshot["narration_source"] = source


@router.post("/{snapshot_id}/period")
def change_report_period(client_id: uuid.UUID, snapshot_id: uuid.UUID, data: PeriodChange, db: Session = Depends(get_db)):
    """Change how many months a draft covers.

    Nothing is pulled: the current month is the draft's own, and every other
    month — in the span and in the span it is compared with — is read from
    its saved (published) report. Headings and ticks are kept.
    """
    report = _load_editable(client_id, snapshot_id, db)
    available = len(periods_svc.timeline(db, client_id, report.end_date))
    if not 1 <= data.months <= available:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Only {available} month{'s' if available != 1 else ''} of data can be combined for this report.",
        )

    # Nothing is pulled: this month is the draft's own, the others are saved.
    snapshot = dict(report.snapshot or {})
    fresh = periods_svc.build_report_data(db, client_id, report.end_date, data.months, live=_live_of(snapshot),
                                          with_page_images=True)
    # What the builder entered for this month is the report's own, whatever
    # span it covers: keywords, prompt checks, links, work, words.
    for keep in ("included_sections", "included_items", "copy", "narration", "narration_source",
                 "rankings", "ai_visibility", "ai_summary", "links", "activities", "hidden_slides", "hidden_cards",
                 "next_month_plan", "plan_source", "subtitle_ai", "subtitles_drafted"):
        if keep in snapshot:
            fresh[keep] = snapshot[keep]
    # This month's own leads, typed or found — kept apart so the month can be
    # published on its own whatever span the report covers.
    was_span = ((snapshot.get("period") or {}).get("months") or 1) > 1
    month_leads = snapshot.get("month_leads") if was_span else composer.lead_values(snapshot)
    month_typed = snapshot.get("month_lead_overrides") if was_span \
        else ((snapshot.get("ga4") or {}).get("lead_overrides") or {})
    fresh["month_leads"] = month_leads or {}
    fresh["month_lead_overrides"] = month_typed or {}
    fresh.pop("span_links", None)
    fresh.pop("span_activities", None)
    ga4_block = dict(fresh.get("ga4") or {})
    if data.months > 1:
        from app.services import sheets as _sheets
        cycles = periods_svc.report_cycles(report.end_date, data.months)[:-1]
        wanted = {_sheets.month_of(end) for _, end in cycles}
        earlier = sorted((r for m, r in _sheets.month_reports(db, client_id).items()
                          if m in wanted and r.id != report.id), key=lambda r: r.end_date)
        fresh["span_links"] = [{**l, "id": f"m{i}-{l.get('id') or j}"} for i, r in enumerate(earlier)
                               for j, l in enumerate((r.snapshot or {}).get("links") or [])]
        fresh["span_activities"] = [a for r in earlier for a in (r.snapshot or {}).get("activities") or []]
        # Leads over the span: each month's own figures — typed or found in its
        # events — added up, so a phone count typed in any month is kept.
        totals = dict(month_leads or {})
        per_month = [composer.lead_values(r.snapshot or {}) for r in earlier]
        for vals in per_month:
            for k, v in vals.items():
                totals[k] = totals.get(k, 0) + v
        ga4_block["lead_overrides"] = {k: round(v) for k, v in totals.items()}
        # Each lead's change: this month against the earlier months' average,
        # kept the way the slides read it (change ÷ (total − change)).
        prev_leads = {}
        for k, total in totals.items():
            earlier_vals = [m.get(k, 0) for m in per_month]
            now = (month_leads or {}).get(k)
            avg = sum(earlier_vals) / len(earlier_vals) if earlier_vals else 0
            if avg and now:
                prev_leads[k] = total * avg / now
        # The total on its own terms, not the sum of the per-type baselines.
        now_all = sum((month_leads or {}).values())
        avg_all = sum(sum(m.values()) for m in per_month) / len(per_month) if per_month else 0
        if avg_all and now_all:
            prev_leads["total"] = sum(totals.values()) * avg_all / now_all
        pv = dict(fresh.get("previous_values") or {})
        pv["leads"] = prev_leads
        fresh["previous_values"] = pv
    else:
        ga4_block["lead_overrides"] = dict(month_typed or {})
    fresh["ga4"] = ga4_block
    if data.months > 1 and isinstance(fresh.get("rankings"), dict):
        cycles = periods_svc.report_cycles(report.end_date, data.months)
        periods_svc._add_cycle_positions(db, client_id, fresh["rankings"], cycles, periods_svc.cycle_labels(cycles))
    # A one-month report keeps its own pages, queries and days; a longer one
    # shows the combined months instead of one month's lists.
    for key in ("trending_pages", "top_queries", "daily"):
        cur = (snapshot.get("gsc") or {}).get(key) if data.months == 1 and (snapshot.get("period") or {}).get("months", 1) == 1 else None
        if cur and isinstance(fresh.get("gsc"), dict) and not fresh["gsc"].get(key):
            fresh["gsc"][key] = cur

    # Every figure just changed, so text the AI wrote against the old ones
    # would contradict the numbers beside it. It is cleared — not rewritten:
    # the AI runs only when someone presses "Write with AI". Anything a
    # person typed is theirs and is left exactly as they left it.
    clear_ai_text(fresh)

    report.start_date = datetime.date.fromisoformat(fresh["period"]["start"])
    report.snapshot = fresh
    flag_modified(report, "snapshot")
    db.commit()
    return get_composer(client_id, snapshot_id, db)


UPLOAD_KINDS = ("gsc", "ga4", "gbp", "rankings", "ai_visibility", "links", "work")


@router.post("/{snapshot_id}/upload/{kind}")
async def upload_to_draft(client_id: uuid.UUID, snapshot_id: uuid.UUID, kind: str,
                          file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Read a sheet into this draft only. Nothing is recorded for the client
    until the report is published."""
    from app.services import draft_uploads as up
    from app.services import sheets
    if kind not in UPLOAD_KINDS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown sheet.")
    report = _load_editable(client_id, snapshot_id, db)
    content = await file.read(up.MAX_SHEET_BYTES + 1)
    snapshot = dict(report.snapshot or {})
    months = (snapshot.get("period") or {}).get("months") or 1
    month = sheets.report_month(report)
    prev_month = (month - datetime.timedelta(days=1)).replace(day=1)
    try:
        table = up.read_table(file.filename or "", content)
        if kind in up.METRIC_SHEETS:
            start = periods_svc.cycle_bounds(report.end_date, 0)[0]
            windows = [(start, report.end_date), periods_svc.previous_window(report.end_date, months)]
            if kind == "gbp":
                # Business Profile sheets are kept by month, dated the 1st.
                windows = [(month, report.end_date), (prev_month, start - datetime.timedelta(days=1))]
            rows = up.metric_rows(kind, table, windows)
            if not rows:
                raise up.SheetError(f"No rows fall in {periods_svc.short_range(*windows[1])} or "
                                    f"{periods_svc.short_range(start, report.end_date)}.")
            current = {k: v for k, v in _live_of(snapshot).items() if k != kind}
            with periods_svc.pulled(rows):
                fresh = periods_svc.build_report_data(db, client_id, report.end_date, months, live=current,
                                                      with_page_images=False)
            snapshot = periods_svc.merge_section(snapshot, fresh, kind)
            done = len({r[1] for r in rows})
            what = f"{done} day{'s' if done != 1 else ''}" if kind != "gbp" else f"{done} month{'s' if done != 1 else ''}"
        elif kind == "rankings":
            done = up.apply_rankings(snapshot, table, month, prev_month)
            what = f"{done} keyword{'s' if done != 1 else ''}"
        elif kind == "ai_visibility":
            done = up.apply_ai(snapshot, table, month)
            what = f"{done} prompt{'s' if done != 1 else ''}"
        elif kind == "links":
            done = up.apply_links(snapshot, table, month)
            what = f"{done} link{'s' if done != 1 else ''}"
        else:
            done = up.apply_work(snapshot, table)
            what = f"{done} task{'s' if done != 1 else ''}"
    except up.SheetError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))

    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return {**get_composer(client_id, snapshot_id, db), "uploaded": what}


@router.put("/{snapshot_id}/narration")
def set_report_narration(client_id: uuid.UUID, snapshot_id: uuid.UUID, data: NarrationUpdate, db: Session = Depends(get_db)):
    """Save hand-edited section commentary. An empty text removes it."""
    report = _load_editable(client_id, snapshot_id, db)
    snapshot = dict(report.snapshot or {})
    narration = dict(snapshot.get("narration") or {})
    source = dict(snapshot.get("narration_source") or {})
    for key, text_ in data.narration.items():
        if key not in composer.NARRATION_KEYS:
            continue
        cleaned = str(text_ or "").strip()[:2000]
        if cleaned == (narration.get(key) or ""):
            continue
        narration[key] = cleaned
        # Clearing a section hands it back to the AI to draft again.
        if cleaned:
            source[key] = composer.NARRATION_EDITED
        else:
            source.pop(key, None)
    snapshot["narration"] = narration
    snapshot["narration_source"] = source
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return {"narration": narration, "narrationSource": source}


@router.post("/{snapshot_id}/narration/{section}/regenerate")
def regenerate_report_narration(client_id: uuid.UUID, snapshot_id: uuid.UUID, section: str, db: Session = Depends(get_db)):
    """Rewrite one section's commentary from its current — possibly edited — figures."""
    if section not in composer.NARRATION_KEYS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown section.")
    report = _load_editable(client_id, snapshot_id, db)
    snapshot = dict(report.snapshot or {})
    client = db.get(Client, client_id)
    try:
        written = generate_section_summaries(
            client.name if client else "", (snapshot.get("period") or _legacy_period(report)).get("label", ""),
            composer.apply_selection(snapshot), [section], composer.current_items(snapshot),
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))
    except Exception:
        logger.exception("Section commentary could not be rewritten.")
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The AI could not write this section just now. Try again.")
    text_ = written.get(section)
    if not text_:
        # Two different failures, and telling them apart is the difference
        # between "add some data" and "press the button again".
        if not composer.narration_availability(snapshot).get(section):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "There are no figures in this block yet, so there is nothing to write about.",
            )
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "The AI did not return a usable paragraph for this block. Try again.",
        )

    narration = dict(snapshot.get("narration") or {})
    source = dict(snapshot.get("narration_source") or {})
    narration[section] = text_
    source[section] = composer.NARRATION_AI
    snapshot["narration"] = narration
    snapshot["narration_source"] = source
    report.snapshot = snapshot
    flag_modified(report, "snapshot")
    db.commit()
    return {"section": section, "text": text_, "source": composer.NARRATION_AI}


@router.get("/history")
def get_report_history(client_id: uuid.UUID, db: Session = Depends(get_db)):
    """Every report of this client, newest first: its period, whether it is
    published, and whether its month is on the sheets."""
    from sqlalchemy.orm import load_only
    from app.models.sheet_cell import SheetCell
    owners = set(db.execute(select(SheetCell.report_id).where(
        SheetCell.client_id == client_id, SheetCell.report_id.is_not(None)).distinct()).scalars())
    out = []
    for r in db.execute(
        select(ReportSnapshot).options(load_only(
            ReportSnapshot.id, ReportSnapshot.start_date, ReportSnapshot.end_date, ReportSnapshot.status,
            ReportSnapshot.generated_at, ReportSnapshot.published_at, ReportSnapshot.snapshot))
        .where(ReportSnapshot.client_id == client_id).order_by(ReportSnapshot.end_date.desc())
    ).scalars():
        period = (r.snapshot or {}).get("period") or {}
        out.append({
            "id": str(r.id), "start_date": r.start_date, "end_date": r.end_date, "status": r.status.value,
            "generated_at": r.generated_at, "published_at": r.published_at,
            "label": period.get("label") or r.end_date.strftime("%B %Y"),
            "range": period.get("range") or periods_svc.short_range(r.start_date, r.end_date),
            "months": period.get("months") or 1,
            "on_sheets": r.id in owners,
        })
    return out


from fastapi.responses import HTMLResponse, StreamingResponse
import io

@router.get("/multi")
def get_multi_report(client_id: uuid.UUID, count: int = 1, db: Session = Depends(get_db)):
    """Fetch multiple snapshots and return them as a unified comparative structure."""
    snapshots = db.execute(
        select(ReportSnapshot).where(ReportSnapshot.client_id == client_id).order_by(ReportSnapshot.end_date.desc()).limit(count)
    ).scalars().all()
    
    if not snapshots:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reports not found.")
        
    snapshots.reverse()
    comparative_data = _build_comparative_report(snapshots)
    return {
        "id": "multi",
        "client_id": str(client_id),
        "status": "published",
        "generated_at": snapshots[-1].generated_at,
        "published_at": snapshots[-1].published_at,
        "end_date": snapshots[-1].end_date,
        "narrative": snapshots[-1].narrative,
        "snapshot": comparative_data
    }


def _load_snapshots(db: Session, client_id: uuid.UUID, count: int, snapshot_id: Optional[uuid.UUID]):
    """Snapshots for a report, oldest first — the order the template renders."""
    if snapshot_id:
        snapshots = db.execute(
            select(ReportSnapshot).where(ReportSnapshot.client_id == client_id, ReportSnapshot.id == snapshot_id)
        ).scalars().all()
    else:
        snapshots = db.execute(
            select(ReportSnapshot).where(ReportSnapshot.client_id == client_id).order_by(ReportSnapshot.end_date.desc()).limit(count)
        ).scalars().all()
    if not snapshots:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reports not found.")
    snapshots.reverse()
    return snapshots


def _report_inputs(request: Request, db: Session, client_id: uuid.UUID, snapshots):
    """Everything report_pdf.html needs. Shared by the PDF download and the
    in-app view so the two render from identical input."""
    import base64

    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found.")

    # Must be set before the logo fetch below — it used to be assigned after,
    # so any client with a relative logo_url failed with UnboundLocalError.
    base_url = str(request.base_url).rstrip("/")

    comparative_data = _build_comparative_report(snapshots)

    client_logo_b64 = ""
    client_logo_url = client.logo_url
    if client_logo_url and client_logo_url.strip():
        import httpx
        fetch_url = base_url + client_logo_url if client_logo_url.startswith("/") else client_logo_url
        try:
            with httpx.Client(timeout=5.0) as c:
                resp = c.get(fetch_url)
                if resp.status_code == 200:
                    b64 = base64.b64encode(resp.content).decode("utf-8")
                    ctype = resp.headers.get("content-type", "image/png")
                    client_logo_b64 = f"data:{ctype};base64,{b64}"
        except Exception:
            pass

    client_data = {
        "name": client.name,
        "domain": client.domain,
        "logo_url": client.logo_url,
        "logo_b64": client_logo_b64,
        "theme_color": client.theme_color,
    }

    # The snapshot stores prompt ids; a report has to print the question that
    # was actually asked, so resolve the text here where the session exists.
    prompt_text = {
        str(pid): text_
        for pid, text_ in db.execute(
            select(AiPrompt.id, AiPrompt.prompt_text).where(AiPrompt.client_id == client_id)
        ).all()
    }
    for row in comparative_data.get("ai_visibility") or []:
        if isinstance(row, dict) and not row.get("prompt"):
            row["prompt"] = prompt_text.get(str(row.get("prompt_id")), "")

    # The report's own slide screenshots (e.g. the Business Profile captures),
    # inlined in slot order so the PDF and the in-app view need no fetches.
    last_id = getattr(snapshots[-1], "id", None)
    if last_id:
        from sqlalchemy.orm import undefer
        for img in db.execute(
            select(ReportImage).options(undefer(ReportImage.data))
            .where(ReportImage.report_id == last_id).order_by(ReportImage.slot)
        ).scalars():
            encoded = base64.b64encode(img.data).decode("ascii")
            comparative_data.setdefault(f"{img.section}_shots", []).append(
                {"src": f"data:{img.mime};base64,{encoded}", "caption": img.caption or ""}
            )

    # The most recent snapshot's cover screenshot, inlined like the rest.
    last = snapshots[-1]
    if getattr(last, "cover_mime", None) and last.cover_image:
        encoded = base64.b64encode(last.cover_image).decode("ascii")
        comparative_data["cover_screenshot"] = f"data:{last.cover_mime};base64,{encoded}"

    return client, comparative_data, client_data, base_url


def _pdf_response(pdf_bytes: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/multi/pdf")
async def download_report_pdf(request: Request, client_id: uuid.UUID, count: int = 1, snapshot_id: Optional[uuid.UUID] = None, db: Session = Depends(get_db)):
    """Generate and return a PDF of the report using Playwright/Chromium."""
    from app.services.pdf_service import generate_report_pdf as gen_pdf

    snapshots = _load_snapshots(db, client_id, count, snapshot_id)
    client, comparative_data, client_data, base_url = _report_inputs(request, db, client_id, snapshots)
    pdf_bytes = await gen_pdf(comparative_data, client_data, base_url)

    safe_name = client.name.replace(" ", "_").replace("/", "_")
    return _pdf_response(pdf_bytes, f"{safe_name}_{count}M_SEO_Report.pdf")


@router.get("/multi/html", response_class=HTMLResponse)
def view_report_html(request: Request, client_id: uuid.UUID, count: int = 1, snapshot_id: Optional[uuid.UUID] = None, db: Session = Depends(get_db)):
    """The PDF's own template as HTML, for showing the report inside the app."""
    from app.services.pdf_service import render_report_html

    snapshots = _load_snapshots(db, client_id, count, snapshot_id)
    _, comparative_data, client_data, base_url = _report_inputs(request, db, client_id, snapshots)
    return HTMLResponse(render_report_html(comparative_data, client_data, base_url))


@router.get("/count")
def get_report_count(client_id: uuid.UUID, db: Session = Depends(get_db)):
    """Fetch the total number of snapshots for the client."""
    count = db.execute(
        select(func.count(ReportSnapshot.id)).where(ReportSnapshot.client_id == client_id)
    ).scalar()
    return {"count": count or 0}

@router.get("/latest")
def get_latest_report(client_id: uuid.UUID, db: Session = Depends(get_db)):
    """Fetch the latest snapshot for the client."""
    report = db.execute(
        select(ReportSnapshot).where(ReportSnapshot.client_id == client_id).order_by(ReportSnapshot.end_date.desc())
    ).scalars().first()
    
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
        
    return {
        "id": report.id,
        "client_id": report.client_id,
        "start_date": report.start_date,
        "end_date": report.end_date,
        "status": report.status,
        "snapshot": report.snapshot,
        "narrative": report.narrative,
        "generated_at": report.generated_at,
        "published_at": report.published_at,
        "published_by": report.published_by
    }


@router.get("/{snapshot_id}/pdf")
async def download_single_report_pdf(request: Request, client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session = Depends(get_db)):
    """Generate and return a PDF of a single report snapshot."""
    from app.services.pdf_service import generate_report_pdf as gen_pdf

    snapshots = _load_snapshots(db, client_id, 1, snapshot_id)
    client, comparative_data, client_data, base_url = _report_inputs(request, db, client_id, snapshots)
    pdf_bytes = await gen_pdf(comparative_data, client_data, base_url)

    safe_name = client.name.replace(" ", "_").replace("/", "_")
    return _pdf_response(pdf_bytes, f"{safe_name}_SEO_Report.pdf")


@router.get("/{snapshot_id}/html", response_class=HTMLResponse)
def view_single_report_html(request: Request, client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session = Depends(get_db)):
    """The PDF's own template as HTML, for showing the report inside the app."""
    from app.services.pdf_service import render_report_html

    snapshots = _load_snapshots(db, client_id, 1, snapshot_id)
    _, comparative_data, client_data, base_url = _report_inputs(request, db, client_id, snapshots)
    return HTMLResponse(render_report_html(comparative_data, client_data, base_url))


@router.get("/{snapshot_id}")
def get_report(client_id: uuid.UUID, snapshot_id: uuid.UUID, db: Session = Depends(get_db)):
    """Fetch a specific report by client and id."""
    report = db.execute(
        select(ReportSnapshot).where(ReportSnapshot.client_id == client_id, ReportSnapshot.id == snapshot_id)
    ).scalar_one_or_none()
    
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found.")
        
    return {
        "id": report.id,
        "client_id": report.client_id,
        "start_date": report.start_date,
        "end_date": report.end_date,
        "status": report.status,
        "snapshot": report.snapshot,
        "narrative": report.narrative,
        "generated_at": report.generated_at,
        "published_at": report.published_at,
        "published_by": report.published_by
    }


# --- Helpers ---

def _compute_kpi_deltas(snapshot: dict, prev_snapshot: dict) -> dict:
    deltas = {}
    for provider in ["gsc", "ga4", "gbp"]:
        deltas[provider] = {}
        for k, v in snapshot[provider].items():
            # Only compute deltas for numeric scalar values, skip lists/dicts (e.g. top_pages)
            if isinstance(v, (int, float)):
                prev_v = prev_snapshot[provider].get(k, 0)
                if isinstance(prev_v, (int, float)):
                    deltas[provider][k] = v - prev_v
    return deltas

def _aggregate_metrics(snapshots, section):
    if not snapshots:
        return {}
        
    count = len(snapshots)
    
    sum_keys = {
        "gsc": ["clicks", "impressions"],
        "ga4": ["sessions", "users", "organic_sessions", "conversions", "ecommerce_events", "revenue",
                "engaged_sessions", "add_to_carts"],
        "gbp": ["views", "searches", "interactions", "calls", "chat_clicks", "direction_requests", "website_clicks", "bookings", "impressions_desktop_maps", "impressions_desktop_search", "impressions_mobile_maps", "impressions_mobile_search"]
    }.get(section, [])
    
    avg_keys = {
        "gsc": ["ctr", "position"],
        "ga4": ["bounce_rate", "session_duration"],
        "gbp": []
    }.get(section, [])
    
    list_keys = {
        "gsc": ["top_pages"],
        "ga4": ["traffic_sources", "devices", "top_pages", "countries"],
        "gbp": []
    }.get(section, [])
    
    # Name-keyed counts rather than a list of rows: GA4 event names are chosen
    # per property, so there is no fixed set to enumerate above.
    dict_keys = {"ga4": ["events"]}.get(section, [])

    list_merge_key = {
        "top_pages": "page",
        "traffic_sources": "source",
        "devices": "device",
        "countries": "country"
    }
    
    list_sum_keys = {
        "top_pages": ["clicks", "impressions", "sessions", "users", "conversions"],
        "traffic_sources": ["sessions", "users", "conversions"],
        "devices": ["sessions", "users", "conversions"],
        "countries": ["sessions", "users", "conversions"]
    }
    
    result = {}
    
    for k in sum_keys + avg_keys:
        result[k] = 0
        
    for s in snapshots:
        data = s.snapshot.get(section, {}) if s.snapshot else {}
        for k in sum_keys:
            val = data.get(k)
            if val is not None:
                result[k] += val
        for k in avg_keys:
            val = data.get(k)
            if val is not None:
                result[k] += val
            
    if count > 0:
        for k in avg_keys:
            result[k] = result[k] / count
            
    for k in dict_keys:
        merged: dict[str, float] = {}
        for s_ in snapshots:
            data = s_.snapshot.get(section, {}) if s_.snapshot else {}
            for name, count_ in (data.get(k) or {}).items():
                merged[name] = merged.get(name, 0) + (count_ or 0)
        if merged:
            result[k] = {n: round(v) for n, v in sorted(merged.items(), key=lambda nv: -nv[1])}

    for k in list_keys:
        merged_list = {}
        for s in snapshots:
            data = s.snapshot.get(section, {}) if s.snapshot else {}
            items = data.get(k, [])
            for item in items:
                m_key_name = list_merge_key.get(k)
                m_key = item.get(m_key_name)
                if not m_key:
                    continue
                if m_key not in merged_list:
                    merged_list[m_key] = dict(item)
                else:
                    for sk in list_sum_keys.get(k, []):
                        if sk in item:
                            merged_list[m_key][sk] = merged_list[m_key].get(sk, 0) + item.get(sk, 0)
                            
        for m_key, m_item in merged_list.items():
            if "bounce_rate" in m_item:
                m_item["bounce_rate"] = m_item["bounce_rate"] / count if count > 0 else 0
                
        if list_sum_keys.get(k):
            sort_key = list_sum_keys[k][0]
            result[k] = sorted(merged_list.values(), key=lambda x: x.get(sort_key, 0), reverse=True)
        else:
            result[k] = list(merged_list.values())

    if count == 1:
        data = snapshots[0].snapshot.get(section, {}) if snapshots[0].snapshot else {}
        for k, v in data.items():
            if k not in result and isinstance(v, (int, float)) and not isinstance(v, bool):
                result[k] = v

    # Trending pages carry their own comparison too.
    if section == "gsc":
        latest = snapshots[-1].snapshot.get(section, {}) if snapshots[-1].snapshot else {}
        for key in ("trending_pages", "daily", "top_queries"):
            if latest.get(key):
                result[key] = latest[key]

    # The GA4 comparison tables (channels, countries) already carry their own
    # previous period, so they are taken from the latest report as it is.
    if section == "ga4":
        from app.services.ga4_service import BREAKDOWNS
        latest = snapshots[-1].snapshot.get(section, {}) if snapshots[-1].snapshot else {}
        for k in BREAKDOWNS:
            for key in (k, f"{k}_previous"):
                if latest.get(key):
                    result[key] = latest[key]
        # Lead figures typed in the builder.
        # (and whether its tables compare against a several-month average.)
        for typed in ("lead_overrides", "lead_overrides_previous", "ai_referral_overrides", "_span_compare"):
            if latest.get(typed):
                result[typed] = latest[typed]

    return result

def _build_comparative_report(snapshots):
    if not snapshots:
        return {}

    class _Composed:
        """A snapshot with unticked rows already removed.

        Filtering once, here, means every downstream aggregation and the PDF
        template all see the same arrays — there is no second place that could
        forget to apply the composer's choices.
        """

        __slots__ = ("snapshot", "end_date", "start_date", "narrative")

        def __init__(self, src):
            self.snapshot = composer.apply_selection(src.snapshot or {})
            self.end_date = src.end_date
            self.start_date = getattr(src, "start_date", src.end_date)
            self.narrative = getattr(src, "narrative", "") or ""

    # The builder has no session of its own; borrow the one these rows are
    # attached to so the trend series can be read without changing callers.
    from sqlalchemy.orm import object_session

    last_client_id = getattr(snapshots[-1], "client_id", None)
    session = object_session(snapshots[-1])
    snapshots = [_Composed(s) for s in snapshots]
    
    months = []
    for s in snapshots:
        months.append(s.end_date.strftime("%B %Y"))
    # A report spanning several cycles names them itself.
    if len(snapshots) == 1:
        labels = ((snapshots[0].snapshot or {}).get("period") or {}).get("labels")
        if isinstance(labels, list) and labels:
            months = [str(l) for l in labels]
        
    comparative_data = {
        "months": months,
        "kpi_deltas": {},
        "rankings": {"summary": {}, "keywords": []},
        "links": [],
        "ai_visibility": [],
        "activities": [],
        "screenshots": []
    }
    
    latest_snap = snapshots[-1].snapshot if snapshots[-1].snapshot else {}
    comparative_data["kpi_deltas"] = latest_snap.get("kpi_deltas", {})
    comparative_data["previous_values"] = latest_snap.get("previous_values") or {}
    comparative_data["ai_summary"] = latest_snap.get("ai_summary") or {}
    comparative_data["hidden_slides"] = latest_snap.get("hidden_slides") or []
    comparative_data["hidden_cards"] = latest_snap.get("hidden_cards") or []

    # Carry the composer's choices into the PDF. For a multi-month export the
    # most recent snapshot's selection wins, since that is the one just edited.
    if isinstance(latest_snap.get("included_sections"), dict):
        comparative_data["included_sections"] = latest_snap["included_sections"]
    if isinstance(latest_snap.get("included_items"), dict):
        comparative_data["included_items"] = latest_snap["included_items"]
    if isinstance(latest_snap.get("copy"), dict):
        comparative_data["copy"] = latest_snap["copy"]
    comparative_data["narration"] = latest_snap.get("narration") if isinstance(latest_snap.get("narration"), dict) else {}
    comparative_data["provenance"] = latest_snap.get("provenance") if isinstance(latest_snap.get("provenance"), dict) else {}
    comparative_data["periods"] = (latest_snap.get("periods") or []) if len(snapshots) == 1 else []
    comparative_data["period"] = latest_snap.get("period") or {}
    # The closing commitment, entered in the builder. Carried through here with
    # the other editorial keys — the report data itself never derives it.
    # The earlier period's AI visibility rate, which the change on that figure
    # is measured against.
    comparative_data["ai_compare"] = (
        latest_snap.get("ai_compare") if isinstance(latest_snap.get("ai_compare"), dict) else {}
    )
    comparative_data["next_month_plan"] = (
        latest_snap.get("next_month_plan") if isinstance(latest_snap.get("next_month_plan"), dict) else {}
    )

    # Daily clicks for the trend chart. Recorded values only — an empty list
    # means the chart is skipped rather than drawn from nothing.
    try:
        first, last = snapshots[0], snapshots[-1]
        if session is None or last_client_id is None:
            raise RuntimeError("no session available for the trend series")
        daily = session.execute(
            select(Metric.captured_on, func.sum(Metric.value))
            .where(
                Metric.client_id == last_client_id,
                Metric.provider == ProviderType.gsc,
                Metric.metric_key == "clicks",
                Metric.dimension_key.is_(None),
                Metric.captured_on >= first.start_date,
                Metric.captured_on <= last.end_date,
            )
            .group_by(Metric.captured_on)
            .order_by(Metric.captured_on)
        ).all()
        comparative_data["gsc_daily"] = [float(v or 0) for _, v in daily]
    except Exception:
        logger.exception("Daily clicks series unavailable for the trend chart.")
        comparative_data["gsc_daily"] = []
    comparative_data["narrative"] = snapshots[-1].narrative if getattr(snapshots[-1], 'narrative', None) else ""
    if "rankings" in latest_snap:
        comparative_data["rankings"]["summary"] = latest_snap["rankings"].get("summary", {})
        comparative_data["rankings"]["summary_overrides"] = latest_snap["rankings"].get("summary_overrides") or {}
        
    comparative_data["gsc"] = _aggregate_metrics(snapshots, "gsc")
    comparative_data["ga4"] = _aggregate_metrics(snapshots, "ga4")
    comparative_data["gbp"] = _aggregate_metrics(snapshots, "gbp")
        
    kw_map = {}
    for idx, s in enumerate(snapshots):
        month = months[idx]
        snap_data = s.snapshot if s.snapshot else {}
        rank_data = snap_data.get("rankings", {}).get("keywords", [])
        for kw in rank_data:
            kid = kw.get("keyword_id")
            if not kid: continue
            if kid not in kw_map:
                kw_map[kid] = {
                    "keyword_id": kid,
                    "term": kw.get("term"),
                    "search_volume": kw.get("search_volume"),
                    "positions": {},
                    "change": None,
                    "initial_rank": kw.get("initial_rank"),
                    "previous_position": kw.get("previous_position"),
                }
            own = kw.get("positions") if isinstance(kw.get("positions"), dict) else None
            if own and len(snapshots) == 1:
                kw_map[kid]["positions"].update(own)
            else:
                kw_map[kid]["positions"][month] = kw.get("position")
            # Update search_volume if it was previously None
            if kw_map[kid]["search_volume"] is None and kw.get("search_volume"):
                kw_map[kid]["search_volume"] = kw.get("search_volume")
            
    latest_rankings = latest_snap.get("rankings", {}).get("keywords", [])
    for kw in latest_rankings:
        kid = kw.get("keyword_id")
        if kid in kw_map:
            kw_map[kid]["change"] = kw.get("change")
            # Preserve the position order from the latest snapshot
            kw_map[kid]["_sort_pos"] = kw.get("position") or 9999
            
    kw_list = list(kw_map.values())
    kw_list.sort(key=lambda x: x.get("_sort_pos", 9999))

    # A one-month report has one position column, so every keyword read as
    # "New". Last month's position is known — typed in the builder or saved
    # with the report — so it gets its own column, named for its month.
    if len(months) == 1 and any(k.get("previous_position") for k in kw_list):
        compare = ((latest_snap.get("period") or {}).get("compare") or {})
        try:
            prev_label = datetime.date.fromisoformat(compare.get("end")).strftime("%B %Y")
        except (TypeError, ValueError):
            prev_label = "Last month"
        if prev_label == months[0]:
            prev_label = compare.get("range") or "Last month"
        for k in kw_list:
            if k.get("previous_position") and prev_label not in k["positions"]:
                k["positions"] = {prev_label: k["previous_position"], **k["positions"]}
        comparative_data["rank_months"] = [prev_label, months[0]]
    comparative_data["rankings"]["keywords"] = kw_list
    
    for idx, s in enumerate(snapshots):
        month = months[idx]
        snap_data = s.snapshot if s.snapshot else {}
        for item in snap_data.get("links", []):
            item_copy = dict(item)
            item_copy["_month"] = month
            comparative_data["links"].append(item_copy)
        for item in snap_data.get("ai_visibility", []):
            item_copy = dict(item)
            item_copy["_month"] = month
            comparative_data["ai_visibility"].append(item_copy)
        for item in snap_data.get("activities", []):
            item_copy = dict(item)
            item_copy["_month"] = month
            comparative_data["activities"].append(item_copy)
        for item in snap_data.get("screenshots", []):
            item_copy = dict(item)
            item_copy["_month"] = month
            comparative_data["screenshots"].append(item_copy)
            
    # Calculate aggregates for the PDF
    ai_vis = comparative_data["ai_visibility"]
    comparative_data["ai_mentioned"] = sum(1 for m in ai_vis if m.get("mentioned"))
    comparative_data["ai_total"] = len(ai_vis)
    comparative_data["ai_platforms"] = len(set(m.get("platform", "") for m in ai_vis))
    
    ai_by_platform = {}
    for m in ai_vis:
        p = m.get("platform", "unknown")
        if p not in ai_by_platform:
            ai_by_platform[p] = {"mentioned": 0, "total": 0}
        ai_by_platform[p]["total"] += 1
        if m.get("mentioned"):
            ai_by_platform[p]["mentioned"] += 1
    comparative_data["ai_by_platform"] = ai_by_platform
    
    links = comparative_data["links"]
    comparative_data["unique_domains"] = len(set(l.get("domain", "") for l in links))
    link_types = {}
    for l in links:
        t = l.get("activity_type", "Other")
        link_types[t] = link_types.get(t, 0) + int(l.get("count") or 1)
    comparative_data["link_types"] = link_types
    
    return comparative_data
