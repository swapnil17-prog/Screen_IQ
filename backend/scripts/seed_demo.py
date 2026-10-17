"""
Seed a demo workspace: one organization, an owner account, two jobs and six
sample candidates screened end-to-end. Idempotent — re-running is a no-op.

    python -m scripts.seed_demo

Credentials default to the values below (override with DEMO_EMAIL / DEMO_PASSWORD).
These are demo-only test credentials for a local instance.
"""

import asyncio
import hashlib
import os
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import Application, Candidate, Job, Organization, User
from app.schemas.organization import OrganizationSettings
from app.services.fairness import analyze_job_description
from app.services.parsing import parse_resume
from app.services.pipeline import prepare_job, run_application

DEMO_EMAIL = os.environ.get("DEMO_EMAIL", "demo@screeniq.dev")
DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "ScreenIQ-demo-2026")
SAMPLES = Path(__file__).resolve().parent.parent / "samples"

JOBS = [
    ("Senior Backend Engineer (Python)", "job_senior_backend.txt", "Engineering", "Remote"),
    ("Data Engineer", "job_data_engineer.txt", "Data", "Seattle · Hybrid"),
]
RESUMES = sorted(p.name for p in SAMPLES.glob("resume_*.txt"))


async def main() -> None:
    async with SessionLocal() as db:
        if await db.scalar(select(User.id).where(User.email == DEMO_EMAIL)):
            print(f"Demo workspace already exists - sign in as {DEMO_EMAIL}")
            return

        org = Organization(name="Acme Talent (Demo)", slug="acme-demo", settings=OrganizationSettings().model_dump())
        db.add(org)
        await db.flush()
        db.add(User(organization_id=org.id, email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD),
                    full_name="Demo Recruiter", role="owner"))

        candidates = []
        for name in RESUMES:
            data = (SAMPLES / name).read_bytes()
            candidate = Candidate(organization_id=org.id, filename=name.replace(".txt", ".pdf"), content_type="text/plain",
                                  file_size=len(data), file_hash=hashlib.sha256(data).hexdigest(),
                                  raw_text=parse_resume(data, name), status="processing", skills=[])
            db.add(candidate)
            candidates.append(candidate)

        jobs = []
        for title, file, department, location in JOBS:
            description = (SAMPLES / file).read_text(encoding="utf-8")
            job = Job(organization_id=org.id, title=title, description=description, department=department,
                      location=location, employment_type="Full-time",
                      bias_report=analyze_job_description(description).model_dump())
            db.add(job)
            jobs.append(job)
        await db.commit()

        app_ids = []
        for job in jobs:
            print(f"Extracting criteria for {job.title}...")
            await prepare_job(db, job)
            for candidate in candidates:
                application = Application(organization_id=org.id, job_id=job.id, candidate_id=candidate.id)
                db.add(application)
                await db.flush()
                app_ids.append(application.id)
        await db.commit()

    print(f"Screening {len(app_ids)} applications...")
    for app_id in app_ids:
        await run_application(app_id)
    print(f"Done. Sign in as {DEMO_EMAIL} (password in scripts/seed_demo.py or $DEMO_PASSWORD).")


if __name__ == "__main__":
    asyncio.run(main())
