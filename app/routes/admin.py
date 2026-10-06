from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.enums import UserRole
from app.dependencies import RequireRole, get_current_user
from app.routes.users import UserResponse
from app.routes.clients import ClientResponse

class ManagerWithDetails(UserResponse):
    managed_users: list[UserResponse] = []
    managed_clients: list[ClientResponse] = []

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(RequireRole([UserRole.super_admin]))]
)

@router.get("/managers", response_model=list[ManagerWithDetails])
def list_managers(db: Session = Depends(get_db)):
    """List all managers."""
    from sqlalchemy.orm import joinedload
    
    managers = db.execute(
        select(User).where(User.role == UserRole.manager).order_by(User.email.asc())
        .options(joinedload(User.managed_users), joinedload(User.managed_clients))
    ).unique().scalars().all()
    
    return managers

from app.core.security import get_password_hash
from app.routes.users import UserCreate
from app.models.client import Client

@router.post("/managers", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_manager(user_in: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Super admin creates a new manager account."""
    if user_in.role != UserRole.manager:
        raise HTTPException(status_code=400, detail="Must specify role as manager")
        
    existing_user = db.execute(select(User).where(User.email == user_in.email)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_manager = User(
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        role=UserRole.manager,
        account_id=current_user.account_id,
        is_active=True
    )
    db.add(new_manager)
    db.commit()
    db.refresh(new_manager)
    return UserResponse(
        id=new_manager.id,
        email=new_manager.email,
        role=new_manager.role,
        client_id=new_manager.client_id,
        is_active=new_manager.is_active,
        last_login_at=None
    )

class ReassignClient(BaseModel):
    manager_id: uuid.UUID

@router.put("/clients/{client_id}/reassign", response_model=dict)
def reassign_client(client_id: uuid.UUID, data: ReassignClient, db: Session = Depends(get_db)):
    """Super admin reassigns a client to a different manager."""
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="This client no longer exists — it may have been deleted. Go back to All Clients.")
        
    manager = db.get(User, data.manager_id)
    if not manager or manager.role != UserRole.manager:
        raise HTTPException(status_code=400, detail="Target user must be a manager")
        
    client.manager_id = manager.id
    db.commit()
    return {"message": "Client reassigned successfully"}
