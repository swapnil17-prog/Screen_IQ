import uuid
from dataclasses import dataclass
from typing import Annotated, TypeVar

import jwt
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AuthError, ForbiddenError, NotFoundError
from app.core.security import decode_access_token
from app.models.base import Base
from app.models.organization import Organization
from app.models.user import User

DB = Annotated[AsyncSession, Depends(get_db)]

M = TypeVar("M", bound=Base)


@dataclass
class AuthContext:
    user: User
    org: Organization

    @property
    def org_id(self) -> uuid.UUID:
        return self.org.id


def _token_from(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return request.cookies.get(settings.auth_cookie_name)


async def get_auth(request: Request, db: DB) -> AuthContext:
    token = _token_from(request)
    if not token:
        raise AuthError("Authentication required.")
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload["sub"])
        org_id = uuid.UUID(payload["org"])
    except (jwt.PyJWTError, KeyError, ValueError) as e:
        raise AuthError("Your session has expired. Please sign in again.") from e

    row = await db.execute(
        select(User, Organization)
        .join(Organization, Organization.id == User.organization_id)
        .where(User.id == user_id, User.organization_id == org_id)
    )
    found = row.first()
    if found is None or not found[0].is_active:
        raise AuthError("Your account is not active. Please sign in again.")
    return AuthContext(user=found[0], org=found[1])


Auth = Annotated[AuthContext, Depends(get_auth)]


def require_roles(*roles: str):
    async def _check(auth: Auth) -> AuthContext:
        if auth.user.role not in roles:
            raise ForbiddenError("You don't have permission to perform this action.")
        return auth

    return _check


# Recruiters can do everything except manage the team / organization settings
Writer = Annotated[AuthContext, Depends(require_roles("owner", "admin", "recruiter"))]
Admin = Annotated[AuthContext, Depends(require_roles("owner", "admin"))]


async def get_owned(db: AsyncSession, model: type[M], obj_id: uuid.UUID, org_id: uuid.UUID, label: str) -> M:
    """Fetch a tenant-owned row, 404ing (not 403) for other tenants' ids."""
    obj = await db.get(model, obj_id)
    if obj is None or getattr(obj, "organization_id", None) != org_id:
        raise NotFoundError(f"{label} not found")
    return obj


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
