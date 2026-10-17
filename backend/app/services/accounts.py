"""
Emailed account links: password reset and teammate invitations.

Tokens are single-use and short-lived; only their SHA-256 is stored. Issuing a new
token revokes the user's earlier unused ones for the same purpose.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import UnprocessableError
from app.core.security import generate_link_token, hash_token
from app.models.user import User
from app.models.user_token import UserToken
from app.services import email as mailer
from app.services.email_templates import Email, compose, first_name_of, hello

logger = logging.getLogger(__name__)

PASSWORD_RESET = "password_reset"
INVITE = "invite"
INVALID_LINK = "This link is invalid or has expired. Request a new one."


def _frontend(path: str, token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}{path}?token={token}"


def reset_link(token: str) -> str:
    return _frontend("/reset-password", token)


def invite_link(token: str) -> str:
    return _frontend("/accept-invite", token)


async def issue_token(db: AsyncSession, user: User, purpose: str, ttl: timedelta) -> str:
    now = datetime.now(UTC)
    await db.execute(
        update(UserToken)
        .where(UserToken.user_id == user.id, UserToken.purpose == purpose, UserToken.used_at.is_(None))
        .values(used_at=now)
    )
    token = generate_link_token()
    db.add(UserToken(user_id=user.id, purpose=purpose, token_hash=hash_token(token), expires_at=now + ttl))
    return token


async def find_token(db: AsyncSession, token: str, purpose: str, *, lock: bool = False) -> tuple[UserToken, User]:
    """Resolve a live token to its user, or raise a generic 'invalid or expired' error."""
    stmt = select(UserToken).where(UserToken.token_hash == hash_token(token), UserToken.purpose == purpose)
    if lock:
        stmt = stmt.with_for_update()
    row = await db.scalar(stmt)
    if row is None or row.used_at is not None or row.expires_at < datetime.now(UTC):
        raise UnprocessableError(INVALID_LINK)
    user = await db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise UnprocessableError(INVALID_LINK)
    return row, user


async def consume_tokens(db: AsyncSession, user: User) -> None:
    """After a password is set, every outstanding reset/invite link for the user stops working."""
    await db.execute(
        update(UserToken).where(UserToken.user_id == user.id, UserToken.used_at.is_(None))
        .values(used_at=datetime.now(UTC))
    )


# ── Emails ───────────────────────────────────────────────────────────────────


def render_password_reset(*, first_name: str | None, link: str) -> Email:
    return compose(
        subject=f"Reset your {settings.app_name} password",
        greeting=hello(first_name),
        paragraphs=[f"We received a request to reset the password for your {settings.app_name} account."],
        button=("Choose a new password", link),
        footnotes=[f"This link expires in {settings.password_reset_ttl_minutes} minutes and can be used once.",
                   "If you didn't ask for this, you can ignore this email: your password won't change."],
        signoff=f"— {settings.app_name}",
    )


def render_invitation(*, first_name: str | None, inviter: str, org_name: str, role: str, link: str) -> Email:
    return compose(
        subject=f"{inviter} invited you to join {org_name} on {settings.app_name}",
        greeting=hello(first_name),
        paragraphs=[
            f"{inviter} has invited you to join the {org_name} hiring workspace on {settings.app_name} "
            f"as {'an' if role == 'admin' else 'a'} {role}.",
            "Accept the invitation to choose your password and sign in.",
        ],
        button=("Accept invitation", link),
        footnotes=[f"This invitation expires in {settings.invite_ttl_days} days. If you weren't expecting it, "
                   "you can ignore this email."],
        signoff=f"— {settings.app_name}",
    )


async def send_password_reset(*, email: str, full_name: str, token: str) -> None:
    """Background task: the request already returned the same response whether or not the account exists."""
    m = render_password_reset(first_name=first_name_of(full_name), link=reset_link(token))
    try:
        await mailer.send_email(to=email, subject=m.subject, text=m.text, html=m.html)
    except mailer.EmailError as e:
        logger.warning("Password reset email to %s not sent: %s", email, e.message)


async def send_invitation(*, user: User, inviter: str, org_name: str, token: str) -> str | None:
    """Returns an error message to show the admin, or None when the email went out."""
    m = render_invitation(first_name=first_name_of(user.full_name), inviter=inviter, org_name=org_name,
                          role=user.role, link=invite_link(token))
    try:
        await mailer.send_email(to=user.email, subject=m.subject, text=m.text, html=m.html)
    except mailer.EmailError as e:
        return e.message
    return None
