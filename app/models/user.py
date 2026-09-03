from __future__ import annotations
from typing import Optional
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import UserRole


class User(Base):
    """Staff user — agency_admin or agency_staff. §11."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True
    )
    manager_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=True, create_constraint=False),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true", nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    account = relationship("Account", back_populates="users")
    published_reports = relationship("ReportSnapshot", back_populates="publisher")
    manager = relationship("User", remote_side=[id], foreign_keys=[manager_id], back_populates="managed_users")
    managed_users = relationship("User", back_populates="manager")
    managed_clients = relationship("Client", foreign_keys="[Client.manager_id]", back_populates="manager")
    project_assignments = relationship("UserProjectAssignment", back_populates="user")
