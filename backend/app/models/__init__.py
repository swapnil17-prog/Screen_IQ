"""Import every model so Base.metadata is complete (Alembic, tests)."""

from app.models.application import Application
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.candidate import Candidate
from app.models.embedding import Embedding
from app.models.evaluation import Evaluation
from app.models.interview import InterviewSession
from app.models.job import Job
from app.models.organization import Organization
from app.models.user import User

__all__ = [
    "Application",
    "AuditLog",
    "Base",
    "Candidate",
    "Embedding",
    "Evaluation",
    "InterviewSession",
    "Job",
    "Organization",
    "User",
]
