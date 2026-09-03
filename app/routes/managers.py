from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
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

@router.post("/assignments", response_model=dict, status_code=status.HTTP_201_CREATED)
def assign_project_to_user(data: AssignmentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Manager assigns a client project to one of their users."""
    
    # 1. Verify manager owns the client
    client = db.get(Client, data.client_id)
    if not client or str(client.manager_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="You do not own this client project")
        
    # 2. Verify manager owns the user
    target_user = db.get(User, data.user_id)
    if not target_user or str(target_user.manager_id) != str(current_user.id):
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
        else:
            # Reassign to new user
            existing_assignment.user_id = data.user_id
            db.commit()
            return {"message": "Project reassigned successfully"}
            
    # 4. Create new mapping if none exists
    assignment = UserProjectAssignment(
        user_id=data.user_id,
        client_id=data.client_id
    )
    db.add(assignment)
    db.commit()
    return {"message": "Project assigned successfully"}

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
