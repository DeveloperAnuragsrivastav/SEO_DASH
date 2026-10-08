from __future__ import annotations
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.client import Client
from app.models.enums import UserRole
from app.models.user_project import UserProjectAssignment
from app.dependencies import RequireRole, get_current_user
from app.core.security import get_password_hash
from app.routes.users import UserCreate, UserResponse
from app.routes.clients import ClientCreate, ClientResponse

class AssignedClient(BaseModel):
    id: uuid.UUID
    name: str
    domain: str

class ManagerUserResponse(UserResponse):
    assigned_clients: list[AssignedClient] = []

router = APIRouter(
    prefix="/managers/me",
    tags=["managers"],
    dependencies=[Depends(RequireRole([UserRole.manager]))]
)

team_router = APIRouter(
    prefix="/team",
    tags=["team"],
    dependencies=[Depends(RequireRole([UserRole.user]))],
)


def assignment_manager(current_user: User, db: Session) -> User:
    """Resolve the active manager without allowing unlinked users into a team."""
    manager = current_user if current_user.role == UserRole.manager else None
    if current_user.role == UserRole.user and current_user.manager_id:
        manager = db.get(User, current_user.manager_id)
    if (
        not manager or manager.role != UserRole.manager or not manager.is_active
        or manager.account_id != current_user.account_id
    ):
        raise HTTPException(status_code=403, detail="An active manager is required to assign projects")
    return manager


@team_router.get("/assignments")
def team_assignment_options(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    manager = assignment_manager(current_user, db)
    members = db.scalars(select(User).where(
        User.manager_id == manager.id, User.account_id == manager.account_id,
        User.role == UserRole.user, User.is_active.is_(True),
    ).order_by(User.email)).all()
    projects = db.scalars(select(Client).where(
        Client.manager_id == manager.id, Client.account_id == manager.account_id,
    ).order_by(Client.name)).all()
    assignments = db.execute(select(UserProjectAssignment).join(Client).where(
        Client.manager_id == manager.id, Client.account_id == manager.account_id,
    )).scalars().all()
    assignees = {str(a.client_id): str(a.user_id) for a in assignments}
    return {
        "users": [{"id": str(u.id), "email": u.email} for u in members],
        "projects": [{"id": str(c.id), "name": c.name, "domain": c.domain,
                      "user_id": assignees.get(str(c.id))} for c in projects],
    }

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_manager_user(user_in: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Manager creates a user under their own manager_id."""
    if user_in.role != UserRole.user:
        raise HTTPException(status_code=400, detail="Managers can only create 'user' roles")
        
    existing_user = db.execute(select(User).where(User.email == user_in.email)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        role=UserRole.user,
        account_id=current_user.account_id,
        manager_id=current_user.id,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        role=new_user.role,
        client_id=new_user.client_id,
        is_active=new_user.is_active,
        last_login_at=None
    )

class AssignmentCreate(BaseModel):
    user_id: uuid.UUID
    client_id: uuid.UUID


class TeamProjectCreate(ClientCreate):
    name: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=1, max_length=255)
    business_type: str = Field(min_length=1, max_length=100)
    locale: str = Field(min_length=1, max_length=35)
    package_keywords: int = Field(ge=0)
    user_id: uuid.UUID | None = None

    model_config = {"extra": "forbid", "str_strip_whitespace": True}


@team_router.post("/projects", response_model=ClientResponse, status_code=201)
def create_team_project(data: TeamProjectCreate, db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    """Create and assign atomically, with ownership derived from the caller's team."""
    manager = assignment_manager(current_user, db)
    target = db.get(User, data.user_id or current_user.id)
    if (not target or target.manager_id != manager.id or target.account_id != manager.account_id
            or target.role != UserRole.user or not target.is_active):
        raise HTTPException(status_code=403, detail="Choose an active user in your team")
    client = Client(
        **data.model_dump(exclude={"user_id"}),
        account_id=manager.account_id, manager_id=manager.id,
        onboarded_at=datetime.now(timezone.utc).date(),
    )
    db.add(client)
    db.flush()
    db.add(UserProjectAssignment(client_id=client.id, user_id=target.id))
    db.commit()
    db.refresh(client)
    return client

@router.post("/assignments", response_model=dict, status_code=status.HTTP_201_CREATED)
@team_router.post("/assignments", response_model=dict, status_code=status.HTTP_201_CREATED)
def assign_project_to_user(data: AssignmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Managers and team members assign projects within their own team."""
    manager = assignment_manager(current_user, db)
    
    # 1. Verify manager owns the client
    # Serialize assignment changes for the same project, including its first assignment.
    client = db.scalar(select(Client).where(Client.id == data.client_id).with_for_update())
    if not client or client.manager_id != manager.id or client.account_id != manager.account_id:
        raise HTTPException(status_code=403, detail="You do not own this client project")
        
    # 2. Verify manager owns the user
    target_user = db.get(User, data.user_id)
    if (not target_user or target_user.manager_id != manager.id
            or target_user.account_id != manager.account_id
            or target_user.role != UserRole.user or not target_user.is_active):
        raise HTTPException(status_code=403, detail="You do not manage this user")
        
    # 3. Check if project is already assigned to ANY user
    existing_assignment = db.execute(
        select(UserProjectAssignment).where(
            UserProjectAssignment.client_id == data.client_id
        )
    ).scalar_one_or_none()
    
    if existing_assignment:
        if str(existing_assignment.user_id) == str(data.user_id):
            return {"message": "User is already assigned to this project"}
        raise HTTPException(status_code=409, detail="This project is already assigned. Unassign the current user first.")
            
    # 4. Create new mapping if none exists
    assignment = UserProjectAssignment(
        user_id=data.user_id,
        client_id=data.client_id
    )
    db.add(assignment)
    db.commit()
    return {"message": "Project assigned successfully"}


@router.delete("/assignments/{project_id}/{user_id}")
@team_router.delete("/assignments/{project_id}/{user_id}")
def unassign_project(project_id: uuid.UUID, user_id: uuid.UUID,
                     db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Remove only the expected assignment; preserve the project and its data."""
    manager = assignment_manager(current_user, db)
    # Team ownership is checked here; project-content access is not required.
    client = db.scalar(select(Client).where(Client.id == project_id).with_for_update())
    if not client or client.manager_id != manager.id or client.account_id != manager.account_id:
        raise HTTPException(status_code=403, detail="This project is outside your team")
    assignment = db.scalar(select(UserProjectAssignment).where(UserProjectAssignment.client_id == project_id))
    if not assignment:
        return {"message": "Project is already unassigned"}
    if assignment.user_id != user_id:
        raise HTTPException(status_code=409, detail="The assignment has changed. Refresh before unassigning.")
    db.delete(assignment)
    db.commit()
    return {"message": "Project unassigned successfully"}

@router.get("/dashboard")
def manager_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Stats for the manager."""
    user_count = db.query(User).filter(User.manager_id == current_user.id).count()
    client_count = db.query(Client).filter(Client.manager_id == current_user.id).count()
    
    return {
        "total_users": user_count,
        "total_projects": client_count
    }

@router.get("/users", response_model=list[ManagerUserResponse])
def get_manager_users(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Get all users managed by the current manager."""
    from sqlalchemy.orm import joinedload
    
    users = db.execute(
        select(User).where(User.manager_id == current_user.id)
        .options(joinedload(User.project_assignments).joinedload(UserProjectAssignment.client))
    ).unique().scalars().all()
    
    result = []
    for u in users:
        clients = [
            AssignedClient(id=pa.client.id, name=pa.client.name, domain=pa.client.domain)
            for pa in u.project_assignments
        ]
        result.append(
            ManagerUserResponse(
                id=u.id,
                email=u.email,
                role=u.role,
                client_id=u.client_id,
                is_active=u.is_active,
                last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
                assigned_clients=clients
            )
        )
    return result
