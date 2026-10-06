from __future__ import annotations
"""Routes for Connection management and verification."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.connection import Connection
from app.models.enums import AccessMode, ConnectionStatus, ProviderType
from app.services.google_clients import (
    ga4_properties, gsc_sites, normalize_ga4, service_account_email, verify_ga4, verify_gbp, verify_gsc,
)
from app.services.crypto import encrypt_credentials
from app.services.dataforseo_auth import validate_dataforseo_credentials

from app.dependencies import RequireRole, check_client_access, get_current_user
from app.models.enums import UserRole
from app.models.user import User

router = APIRouter(
    prefix="/clients/{client_id}/connections",
    tags=["connections"],
    dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))]
)
read_router = APIRouter(
    prefix="/clients/{client_id}/connections",
    tags=["connections"],
    dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))]
)
verify_router = APIRouter(
    prefix="/connections",
    tags=["connections_verify"],
    dependencies=[Depends(RequireRole([UserRole.super_admin, UserRole.manager, UserRole.user]))]
)

# Schemas
class ConnectionCreate(BaseModel):
    provider: ProviderType
    property_id: str
    property_tz: str | None = None

class ConnectionUpdate(BaseModel):
    property_id: str | None = None
    property_tz: str | None = None

class ConnectionResponse(BaseModel):
    id: uuid.UUID
    client_id: uuid.UUID
    provider: ProviderType
    access_mode: AccessMode
    property_id: str
    property_tz: str | None
    status: ConnectionStatus
    last_verified_at: datetime | None
    last_error: str | None

    model_config = {"from_attributes": True}


class DataForSEOConnectionCreate(BaseModel):
    access_mode: AccessMode
    login: str | None = None
    password: str | None = None

class DataForSEOConnectionUpdate(BaseModel):
    access_mode: AccessMode
    login: str | None = None
    password: str | None = None


@router.post("", response_model=ConnectionResponse, status_code=201)
def create_connection(
    client_id: uuid.UUID,
    data: ConnectionCreate,
    db: Session = Depends(get_db),
) -> Connection:
    """Create a new service-account connection for a client."""
    if data.provider == ProviderType.dataforseo:
        raise HTTPException(
            status_code=400, detail="DataForSEO connections are handled separately."
        )

    raw = (data.property_id or "").strip()
    if not raw:
        raise HTTPException(status_code=422, detail="Type the property — the website address for Search Console, the property ID for Analytics.")
    if data.provider == ProviderType.ga4:
        # A wrong kind of ID (G-…, UA-…, text) can never be read: say so now.
        try:
            raw = normalize_ga4(raw)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    elif data.provider == ProviderType.gsc:
        from app.services.google_clients import _gsc_domain
        domain = _gsc_domain(raw)
        if not domain or "." not in domain or " " in domain:
            raise HTTPException(status_code=422, detail=f"“{raw}” is not a website address. Type it like foodbazaar.co.uk or https://foodbazaar.co.uk/.")

    conn = Connection(
        client_id=client_id,
        provider=data.provider,
        access_mode=AccessMode.platform_shared,
        property_id=raw,
        property_tz=_check_timezone(data.property_tz),
        status=ConnectionStatus.not_connected,
    )

    # Check it at the moment it is mapped. Saving a property id is not the
    # same as being able to read it, and leaving that unanswered until
    # somebody presses Verify means a typo looks identical to a property the
    # client has not shared yet. The row is still saved either way — mapping
    # ahead of the client granting access is a normal thing to do — but the
    # status and the message it carries are true straight away.
    _run_verification(conn)

    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


def _owned_connection(connection_id: uuid.UUID, db: Session, user: User) -> Connection:
    """A connection the signed-in person may act on — its client must be
    theirs, the same rule as every /clients/{id} page. 404 otherwise."""
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="This connection no longer exists — refresh the Connections page.")
    check_client_access(user, conn.client_id, db)
    return conn


def _check_timezone(tz: str | None) -> str | None:
    """A timezone people typed, checked against the IANA list."""
    if not tz:
        return None
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        ZoneInfo(tz.strip())
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(status_code=422, detail=f"“{tz}” is not a timezone. Pick one from the list, e.g. Europe/London or Asia/Kolkata.")
    return tz.strip()


def _run_verification(conn: Connection) -> None:
    """Test the connection against Google and record the outcome on it.

    Shared by mapping and the Verify button so the two can never disagree
    about what counts as connected. Whatever format was typed, the property
    is stored the way Google names it once it is found (foodbazaar.co.uk →
    sc-domain:foodbazaar.co.uk or https://foodbazaar.co.uk/), and a GA4
    property's timezone is taken from Google.
    """
    if conn.provider not in (ProviderType.gsc, ProviderType.ga4, ProviderType.gbp):
        return

    try:
        if conn.provider == ProviderType.gsc:
            conn.property_id = verify_gsc(conn.property_id)
        elif conn.provider == ProviderType.ga4:
            conn.property_id = normalize_ga4(conn.property_id)
            conn.property_tz = verify_ga4(conn.property_id) or conn.property_tz
        elif conn.provider == ProviderType.gbp:
            verify_gbp(conn.property_id)
    except ValueError as e:
        conn.status = ConnectionStatus.error
        conn.last_error = str(e)
        return
    except Exception as e:  # a network or client-library failure, not a rejection
        conn.status = ConnectionStatus.error
        conn.last_error = f"Could not reach Google to check this property — try Verify again in a minute. ({type(e).__name__})"
        return

    conn.status = ConnectionStatus.connected
    conn.last_verified_at = datetime.now(timezone.utc)
    conn.last_error = None


@verify_router.get("/google/options")
def google_options(provider: str):
    """Helpers for the Map Property form: the service-account address to share
    with, and the properties it can already read — so the right one can be
    picked rather than typed."""
    out: dict = {"email": service_account_email(), "properties": [], "error": None}
    try:
        if provider == "gsc":
            out["properties"] = [{"value": s_["property"], "label": s_["property"]} for s_ in gsc_sites()]
        elif provider == "ga4":
            out["properties"] = [{"value": p_["property"], "label": f"{p_['name']} · {p_['property']}", "account": p_["account"]}
                                 for p_ in ga4_properties()]
    except ValueError as e:
        out["error"] = str(e)
    except Exception as e:
        out["error"] = f"Could not reach Google to list properties ({type(e).__name__})."
    return out


@read_router.get("", response_model=list[ConnectionResponse])
def list_connections(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[Connection]:
    """List all connections for a client."""
    return db.query(Connection).filter(Connection.client_id == client_id).all()


@verify_router.patch("/{connection_id}", response_model=ConnectionResponse)
def update_connection(
    connection_id: uuid.UUID,
    data: ConnectionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Connection:
    """Update connection properties. Modifying property_id resets status."""
    conn = _owned_connection(connection_id, db, user)
    if not conn:
        raise HTTPException(status_code=404, detail="This connection no longer exists — refresh the Connections page.")

    if data.property_id is not None and data.property_id != conn.property_id:
        conn.property_id = data.property_id
        conn.status = ConnectionStatus.not_connected
        conn.last_verified_at = None
        conn.last_error = None

    if data.property_tz is not None:
        conn.property_tz = _check_timezone(data.property_tz)

    db.commit()
    db.refresh(conn)
    return conn


@verify_router.post("/{connection_id}/verify", response_model=ConnectionResponse)
def verify_connection(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Connection:
    """Trigger an immediate, lightweight verification call to Google."""
    conn = _owned_connection(connection_id, db, user)
    if not conn:
        raise HTTPException(status_code=404, detail="This connection no longer exists — refresh the Connections page.")

    if conn.provider not in (ProviderType.gsc, ProviderType.ga4, ProviderType.gbp):
        raise HTTPException(
            status_code=400, detail="Verification only supported for Google providers in this phase."
        )

    _run_verification(conn)

    db.commit()
    db.refresh(conn)

    # Return 400 so the caller knows it failed immediately,
    # but the DB record is already updated.
    if conn.status == ConnectionStatus.error:
        raise HTTPException(status_code=400, detail=conn.last_error)

    return conn


class PullRequest(BaseModel):
    start_date: str  # ISO date YYYY-MM-DD
    end_date: str

class PullResponse(BaseModel):
    status: str
    rows_inserted: int

@verify_router.post("/{connection_id}/pull", response_model=PullResponse)
def trigger_pull(
    connection_id: uuid.UUID,
    data: PullRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Test a connection by pulling a window. Nothing is stored — reports keep
    what they pull, and only published months reach the sheets."""
    conn = _owned_connection(connection_id, db, user)
    if not conn:
        raise HTTPException(status_code=404, detail="This connection no longer exists — refresh the Connections page.")

    from datetime import date
    try:
        sd = date.fromisoformat(data.start_date)
        ed = date.fromisoformat(data.end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, must be YYYY-MM-DD")

    if conn.provider == ProviderType.gsc:
        from app.services.gsc_service import pull_gsc_data
        try:
            result = pull_gsc_data(db, connection_id, sd, ed)
            return {"status": "success", "rows_inserted": len(result.get("rows") or [])}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif conn.provider == ProviderType.ga4:
        from app.services.ga4_service import pull_ga4_data
        try:
            result = pull_ga4_data(db, connection_id, sd, ed)
            return {"status": "success", "rows_inserted": len(result.get("rows") or [])}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif conn.provider == ProviderType.gbp:
        from app.services.gbp_service import pull_gbp_data
        try:
            rows = pull_gbp_data(db, connection_id, sd, ed)
            return {"status": "success", "rows_inserted": len(rows)}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Unsupported provider for pull")


@router.post("/dataforseo", response_model=ConnectionResponse, status_code=201)
def create_dataforseo_connection(
    client_id: uuid.UUID,
    data: DataForSEOConnectionCreate,
    db: Session = Depends(get_db),
) -> Connection:
    """Create a DataForSEO connection."""
    # Validate credentials if client-owned
    if data.access_mode == AccessMode.client_owned:
        if not data.login or not data.password:
            raise HTTPException(status_code=400, detail="login and password required for client_owned mode")
        try:
            validate_dataforseo_credentials(data.login, data.password)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        credentials_blob = encrypt_credentials({"login": data.login, "password": data.password})
        status = ConnectionStatus.connected
        last_error = None
        last_verified_at = datetime.now(timezone.utc)
    else:
        # Platform shared
        credentials_blob = None
        # We don't necessarily validate the platform credentials here inline, 
        # but we could. For now, mark connected if platform shared.
        status = ConnectionStatus.connected
        last_error = None
        last_verified_at = datetime.now(timezone.utc)

    conn = Connection(
        client_id=client_id,
        provider=ProviderType.dataforseo,
        access_mode=data.access_mode,
        property_id="dataforseo_account",  # Not really used for DataForSEO
        credentials=credentials_blob,
        status=status,
        last_verified_at=last_verified_at,
        last_error=last_error
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@verify_router.put("/{connection_id}/dataforseo", response_model=ConnectionResponse)
def update_dataforseo_connection(
    connection_id: uuid.UUID,
    data: DataForSEOConnectionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Connection:
    """Update a DataForSEO connection (access mode / credentials)."""
    conn = _owned_connection(connection_id, db, user)
    if not conn or conn.provider != ProviderType.dataforseo:
        raise HTTPException(status_code=404, detail="DataForSEO connection not found")

    if data.access_mode == AccessMode.client_owned:
        if not data.login or not data.password:
            raise HTTPException(status_code=400, detail="login and password required for client_owned mode")
        try:
            validate_dataforseo_credentials(data.login, data.password)
        except ValueError as e:
            # Explicitly set error state if validation fails
            conn.status = ConnectionStatus.error
            conn.last_error = str(e)
            db.commit()
            raise HTTPException(status_code=400, detail=str(e))
        
        conn.credentials = encrypt_credentials({"login": data.login, "password": data.password})
        conn.access_mode = data.access_mode
        conn.status = ConnectionStatus.connected
        conn.last_error = None
        conn.last_verified_at = datetime.now(timezone.utc)
    else:
        # Switching to platform shared
        conn.access_mode = data.access_mode
        conn.credentials = None
        conn.status = ConnectionStatus.connected
        conn.last_error = None
        conn.last_verified_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(conn)
    return conn

@verify_router.delete("/{connection_id}")
def delete_connection(
    connection_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a connection record."""
    conn = _owned_connection(connection_id, db, user)
    if not conn:
        raise HTTPException(status_code=404, detail="This connection no longer exists — refresh the Connections page.")
        
    db.delete(conn)
    db.commit()
    return {"status": "success", "message": "Connection deleted"}

