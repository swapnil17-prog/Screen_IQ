import re
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import DB, Auth, client_ip
from app.core.config import settings
from app.core.errors import AuthError, ConflictError, ForbiddenError
from app.core.rate_limit import RateLimiter
from app.core.security import burn_password_check, create_access_token, hash_password, verify_password
from app.models.organization import Organization
from app.models.user import User
from app.schemas.api import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    InvitationOut,
    LoginRequest,
    MeOut,
    OrganizationOut,
    RegisterRequest,
    SessionOut,
    TokenPasswordRequest,
    UserOut,
)
from app.schemas.organization import OrganizationSettings
from app.services import accounts, audit, tasks

router = APIRouter(prefix="/auth", tags=["auth"])
limit_auth = Depends(RateLimiter(settings.rate_limit_auth_per_minute, scope="auth"))


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
    return slug or "org"


def _session(response: Response, user: User, org: Organization) -> SessionOut:
    token = create_access_token(user.id, org.id, user.role)
    response.set_cookie(
        settings.auth_cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_ttl_minutes * 60,
        path="/",
    )
    return SessionOut(
        user=UserOut.model_validate(user), organization=OrganizationOut.model_validate(org), access_token=token
    )


@router.post("/register", response_model=SessionOut, status_code=status.HTTP_201_CREATED, dependencies=[limit_auth])
async def register(body: RegisterRequest, request: Request, response: Response, db: DB) -> SessionOut:
    """Create a new organization with its first (owner) user."""
    if not settings.allow_public_signup:
        raise ForbiddenError("Self-service sign-up is disabled. Ask an administrator for an invite.")
    email = body.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise ConflictError("An account with this email already exists.")

    slug = _slugify(body.organization_name)
    if await db.scalar(select(Organization.id).where(Organization.slug == slug)):
        slug = f"{slug}-{secrets.token_hex(3)}"
    org = Organization(name=body.organization_name.strip(), slug=slug, settings=OrganizationSettings().model_dump())
    db.add(org)
    await db.flush()
    user = User(
        organization_id=org.id,
        email=email,
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
        role="owner",
        last_login_at=datetime.now(UTC),
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as e:
        await db.rollback()
        raise ConflictError("An account with this email already exists.") from e
    audit.record(db, organization_id=org.id, actor_user_id=user.id, action="organization.created",
                 entity_type="organization", entity_id=org.id, ip_address=client_ip(request))
    await db.commit()
    await db.refresh(user)
    await db.refresh(org)
    return _session(response, user, org)


@router.post("/login", response_model=SessionOut, dependencies=[limit_auth])
async def login(body: LoginRequest, request: Request, response: Response, db: DB) -> SessionOut:
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None:
        burn_password_check(body.password)
        raise AuthError("Incorrect email or password.")
    if not verify_password(body.password, user.password_hash):
        raise AuthError("Incorrect email or password.")
    if not user.is_active:
        raise AuthError("This account has been deactivated. Contact your administrator.")
    org = await db.get(Organization, user.organization_id)
    user.last_login_at = datetime.now(UTC)
    audit.record(db, organization_id=user.organization_id, actor_user_id=user.id, action="user.login",
                 entity_type="user", entity_id=user.id, ip_address=client_ip(request))
    await db.commit()
    await db.refresh(user)
    return _session(response, user, org)  # type: ignore[arg-type]


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    response.delete_cookie(settings.auth_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=MeOut)
async def me(auth: Auth) -> MeOut:
    return MeOut(user=UserOut.model_validate(auth.user), organization=OrganizationOut.model_validate(auth.org))


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT, dependencies=[limit_auth])
async def change_password(body: ChangePasswordRequest, auth: Auth, request: Request, db: DB) -> Response:
    user = await db.get(User, auth.user.id)
    if user is None or not verify_password(body.current_password, user.password_hash):
        raise AuthError("Your current password is incorrect.")
    user.password_hash = hash_password(body.new_password)
    audit.record(db, organization_id=auth.org_id, actor_user_id=user.id, action="user.password_changed",
                 entity_type="user", entity_id=user.id, ip_address=client_ip(request))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT, dependencies=[limit_auth])
async def forgot_password(body: ForgotPasswordRequest, request: Request, db: DB) -> Response:
    """Email a reset link. Responds the same whether or not the account exists."""
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    if user is not None and user.is_active:
        token = await accounts.issue_token(db, user, accounts.PASSWORD_RESET,
                                           timedelta(minutes=settings.password_reset_ttl_minutes))
        audit.record(db, organization_id=user.organization_id, actor_user_id=user.id,
                     action="user.password_reset_requested", entity_type="user", entity_id=user.id,
                     ip_address=client_ip(request))
        await db.commit()
        tasks.spawn(accounts.send_password_reset(email=user.email, full_name=user.full_name, token=token),
                    name=f"password-reset-{user.id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT, dependencies=[limit_auth])
async def reset_password(body: TokenPasswordRequest, request: Request, db: DB) -> Response:
    _, user = await accounts.find_token(db, body.token, accounts.PASSWORD_RESET, lock=True)
    user.password_hash = hash_password(body.password)
    await accounts.consume_tokens(db, user)
    audit.record(db, organization_id=user.organization_id, actor_user_id=user.id, action="user.password_reset",
                 entity_type="user", entity_id=user.id, ip_address=client_ip(request))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/invitations/{token}", response_model=InvitationOut, dependencies=[limit_auth])
async def get_invitation(token: str, db: DB) -> InvitationOut:
    _, user = await accounts.find_token(db, token, accounts.INVITE)
    org = await db.get(Organization, user.organization_id)
    return InvitationOut(email=user.email, full_name=user.full_name, organization_name=org.name if org else "")


@router.post("/accept-invite", response_model=SessionOut, dependencies=[limit_auth])
async def accept_invite(body: TokenPasswordRequest, request: Request, response: Response, db: DB) -> SessionOut:
    """Set a password from the emailed invitation and sign straight in."""
    _, user = await accounts.find_token(db, body.token, accounts.INVITE, lock=True)
    user.password_hash = hash_password(body.password)
    user.last_login_at = datetime.now(UTC)
    await accounts.consume_tokens(db, user)
    audit.record(db, organization_id=user.organization_id, actor_user_id=user.id, action="user.invite_accepted",
                 entity_type="user", entity_id=user.id, ip_address=client_ip(request))
    await db.commit()
    await db.refresh(user)
    org = await db.get(Organization, user.organization_id)
    return _session(response, user, org)  # type: ignore[arg-type]
