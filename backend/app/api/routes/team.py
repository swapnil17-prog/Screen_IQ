import uuid

from fastapi import APIRouter, Request, status
from sqlalchemy import select

from app.api.deps import DB, Admin, Auth, client_ip, get_owned
from app.core.errors import ConflictError, ForbiddenError
from app.core.security import hash_password
from app.models.organization import Organization
from app.models.user import User
from app.schemas.api import InviteUserRequest, OrganizationOut, OrganizationUpdate, UpdateUserRequest, UserOut
from app.services import audit

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


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def invite_user(body: InviteUserRequest, auth: Admin, request: Request, db: DB) -> UserOut:
    """Add a teammate with a temporary password (share it with them securely)."""
    email = body.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise ConflictError("A user with this email already exists.")
    user = User(
        organization_id=auth.org_id,
        email=email,
        full_name=body.full_name.strip(),
        role=body.role,
        password_hash=hash_password(body.temporary_password),
    )
    db.add(user)
    await db.flush()
    audit.record(db, organization_id=auth.org_id, actor_user_id=auth.user.id, action="user.invited",
                 entity_type="user", entity_id=user.id, details={"role": body.role}, ip_address=client_ip(request))
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


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
