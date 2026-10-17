import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request, status
from sqlalchemy import select

from app.api.deps import DB, Admin, Auth, AuthContext, client_ip, get_owned
from app.core.config import settings
from app.core.errors import ConflictError, ForbiddenError, UnprocessableError
from app.core.security import hash_password
from app.models.organization import Organization
from app.models.user import User
from app.schemas.api import (
    InviteUserRequest,
    InviteUserResult,
    OrganizationOut,
    OrganizationUpdate,
    UpdateUserRequest,
    UserOut,
)
from app.services import accounts, audit

router = APIRouter(tags=["organization"])


@router.get("/organization", response_model=OrganizationOut)
async def get_organization(auth: Auth) -> OrganizationOut:
    return OrganizationOut.model_validate(auth.org)


@router.patch("/organization", response_model=OrganizationOut)
async def update_organization(body: OrganizationUpdate, auth: Admin, request: Request, db: DB) -> OrganizationOut:
    org = await db.get(Organization, auth.org_id)
    changes: dict = {}
    if body.name is not None:
        org.name = body.name.strip()  # type: ignore[union-attr]
        changes["name"] = org.name  # type: ignore[union-attr]
    if body.settings is not None:
        org.settings = body.settings.model_dump()  # type: ignore[union-attr]
        changes["settings"] = org.settings  # type: ignore[union-attr]
    audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="organization.updated",
                 entity_type="organization", entity_id=auth.org_id, details=changes, ip_address=client_ip(request))
    await db.commit()
    await db.refresh(org)
    return OrganizationOut.model_validate(org)


@router.get("/users", response_model=list[UserOut])
async def list_users(auth: Auth, db: DB) -> list[UserOut]:
    rows = await db.scalars(select(User).where(User.organization_id == auth.org_id).order_by(User.created_at))
    return [UserOut.model_validate(u) for u in rows]


async def _send_invite(db: DB, user: User, auth: AuthContext) -> InviteUserResult:
    token = await accounts.issue_token(db, user, accounts.INVITE, timedelta(days=settings.invite_ttl_days))
    await db.commit()
    error = await accounts.send_invitation(user=user, inviter=auth.user.full_name, org_name=auth.org.name, token=token)
    return InviteUserResult(user=UserOut.model_validate(user), invite_link=accounts.invite_link(token),
                            invite_emailed=error is None and settings.email_delivery == "smtp", email_error=error)


@router.post("/users", response_model=InviteUserResult, status_code=status.HTTP_201_CREATED)
async def invite_user(body: InviteUserRequest, auth: Admin, request: Request, db: DB) -> InviteUserResult:
    """Invite a teammate by email (they choose their password), or create them with a temporary password."""
    email = body.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise ConflictError("A user with this email already exists.")
    by_email = body.temporary_password is None
    user = User(
        organization_id=auth.org_id,
        email=email,
        full_name=body.full_name.strip(),
        role=body.role,
        # Invitees get an unusable random password until they accept
        password_hash=hash_password(body.temporary_password or secrets.token_urlsafe(32)),
        invited_at=datetime.now(UTC) if by_email else None,
    )
    db.add(user)
    await db.flush()
    audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="user.invited",
                 entity_type="user", entity_id=user.id, details={"role": body.role, "by_email": by_email},
                 ip_address=client_ip(request))
    await db.commit()
    await db.refresh(user)
    if not by_email:
        return InviteUserResult(user=UserOut.model_validate(user))
    return await _send_invite(db, user, auth)


@router.post("/users/{user_id}/resend-invite", response_model=InviteUserResult)
async def resend_invite(user_id: uuid.UUID, auth: Admin, db: DB) -> InviteUserResult:
    """Email a fresh invitation link; earlier links stop working."""
    user = await get_owned(db, User, user_id, auth.org_id, "User")
    if user.invited_at is None or user.last_login_at is not None or not user.is_active:
        raise UnprocessableError("This teammate has no pending invitation.")
    return await _send_invite(db, user, auth)


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, body: UpdateUserRequest, auth: Admin, request: Request, db: DB) -> UserOut:
    user = await get_owned(db, User, user_id, auth.org_id, "User")
    if user.role == "owner" and (body.role is not None or body.is_active is False):
        raise ForbiddenError("The organization owner's role and status can't be changed.")
    if user.id == auth.user.id and body.is_active is False:
        raise ForbiddenError("You can't deactivate your own account.")
    changes = body.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(user, field, value)
    audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="user.updated",
                 entity_type="user", entity_id=user.id, details=changes, ip_address=client_ip(request))
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)
