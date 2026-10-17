import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


def record(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    actor_type: str = "user",
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Stage an audit entry on the session; it commits with the surrounding unit of work."""
    db.add(
        AuditLog(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type=actor_type,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
            ip_address=ip_address,
        )
    )
