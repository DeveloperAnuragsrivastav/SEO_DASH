from __future__ import annotations
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.user import User
from app.models.enums import UserRole
from app.dependencies import RequireRole
from app.core.security import get_password_hash

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(RequireRole([UserRole.super_admin]))]
)

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole
    client_id: uuid.UUID | None = None

class UserUpdateRole(BaseModel):
    role: UserRole

class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole
    client_id: uuid.UUID | None = None
    is_active: bool
    last_login_at: datetime | None = None

    class Config:
        from_attributes = True

@router.get("", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db)):
    """List all users."""
    users = db.execute(
        select(User).order_by(User.email.asc())
    ).scalars().all()
    
    return [
        UserResponse(
            id=u.id,
            email=u.email,
            role=u.role,
            client_id=u.client_id,
            is_active=u.is_active,
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None
        ) for u in users
    ]

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    """Create a new user. The first account is assumed to be the agency account."""
    from app.models.account import Account
    account = db.execute(select(Account)).scalars().first()
    if not account:
        raise HTTPException(status_code=500, detail="System account not configured")
        
    existing = db.execute(select(User).where(User.email == user_in.email)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    new_user = User(
        account_id=account.id,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        role=user_in.role,
        client_id=user_in.client_id if user_in.role == UserRole.manager else None,
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

@router.put("/{user_id}/role", response_model=UserResponse)
def update_user_role(user_id: uuid.UUID, role_in: UserUpdateRole, db: Session = Depends(get_db)):
    """Promote or demote a user."""
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.role = role_in.role
    db.commit()
    db.refresh(user)
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        client_id=user.client_id,
        is_active=user.is_active,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None
    )

@router.put("/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(user_id: uuid.UUID, db: Session = Depends(get_db)):
    """Soft-delete a user."""
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.is_active = False
    db.commit()
    db.refresh(user)
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None
    )
