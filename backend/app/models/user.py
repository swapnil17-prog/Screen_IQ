from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScoped, Timestamps, UUIDPk

ROLES = ("owner", "admin", "recruiter", "viewer")


class User(UUIDPk, TenantScoped, Timestamps, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(Text, nullable=False)  # stored lower-cased
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="recruiter")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set when added by email invitation; the invite is pending until they first sign in
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Emails are globally unique so login needs no org selector.
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)
