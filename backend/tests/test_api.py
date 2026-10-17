"""
End-to-end API tests against a real Postgres + pgvector (see conftest.py).

Covers the whole product loop — auth, JD extraction & bias report, resume upload,
background screening with RAG, explainable scores, AI interview over the public
link, LLM-judge evaluation with counterfactual bias audit — plus tenant
isolation, RBAC and right-to-erasure.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select, text

pytestmark = pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")

from app.core.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base, Embedding  # noqa: E402
from app.services import tasks  # noqa: E402
from tests.conftest import read_sample  # noqa: E402

API = "/api/v1"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def register(client: httpx.AsyncClient, org: str = "Acme") -> dict:
    email = f"owner-{uuid.uuid4().hex[:8]}@example.com"
    r = await client.post(f"{API}/auth/register", json={
        "organization_name": org, "full_name": "Owner Person", "email": email, "password": "Passw0rd!x",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    return {"headers": {"Authorization": f"Bearer {body['access_token']}"}, "email": email, "session": body}


async def create_ready_job(client, headers) -> dict:
    r = await client.post(f"{API}/jobs", headers=headers, json={
        "title": "Senior Backend Engineer (Python)", "description": read_sample("job_senior_backend.txt"),
        "department": "Engineering", "location": "Remote",
    })
    assert r.status_code == 201, r.text
    await tasks.wait_all()
    job = (await client.get(f"{API}/jobs/{r.json()['id']}", headers=headers)).json()
    assert job["extraction_status"] == "completed", job
    return job


async def upload(client, headers, job_id: str, names: list[str], extra: list | None = None) -> dict:
    files = [("files", (n, read_sample(n).encode(), "text/plain")) for n in names] + (extra or [])
    r = await client.post(f"{API}/jobs/{job_id}/applications/upload", headers=headers, files=files)
    assert r.status_code == 201, r.text
    await tasks.wait_all()
    return r.json()


async def test_health_and_meta(client):
    assert (await client.get(f"{API}/health")).json() == {"status": "ok"}
    ready = await client.get(f"{API}/health/ready")
    assert ready.status_code == 200 and ready.json()["pgvector"] is True
    meta = (await client.get(f"{API}/meta")).json()
    assert meta["llm_provider"] == "mock" and meta["embedding_provider"] == "hash"


async def test_auth_flow(client):
    owner = await register(client)
    me = await client.get(f"{API}/auth/me", headers=owner["headers"])
    assert me.status_code == 200 and me.json()["user"]["role"] == "owner"

    # cookie session works too
    assert (await client.get(f"{API}/auth/me")).status_code == 200
    client.cookies.clear()

    bad = await client.post(f"{API}/auth/login", json={"email": owner["email"], "password": "nope-nope-1"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "unauthorized"
    good = await client.post(f"{API}/auth/login", json={"email": owner["email"], "password": "Passw0rd!x"})
    assert good.status_code == 200

    dup = await client.post(f"{API}/auth/register", json={
        "organization_name": "Other", "full_name": "X", "email": owner["email"], "password": "Passw0rd!x"})
    assert dup.status_code == 409

    weak = await client.post(f"{API}/auth/register", json={
        "organization_name": "Other", "full_name": "X", "email": "weak@example.com", "password": "short"})
    assert weak.status_code == 422 and weak.json()["error"]["code"] == "validation_error"

    client.cookies.clear()
    assert (await client.get(f"{API}/jobs")).status_code == 401


async def test_full_hiring_pipeline(client):
    owner = await register(client)
    h = owner["headers"]
    job = await create_ready_job(client, h)
    assert "Python" in job["extracted"]["required_skills"]
    assert job["bias_report"]["rating"] == "inclusive"

    result = await upload(
        client, h, job["id"],
        ["resume_ada_strong.txt", "resume_ben_partial.txt", "resume_chloe_weak.txt"],
        extra=[("files", ("photo.png", b"\x89PNG....", "image/png"))],
    )
    assert len(result["created"]) == 3
    assert result["errors"][0]["filename"] == "photo.png"

    apps = (await client.get(f"{API}/jobs/{job['id']}/applications", headers=h)).json()
    assert [a["status"] for a in apps] == ["completed"] * 3, apps
    names = [a["candidate"]["full_name"] for a in apps]
    assert names == ["Ada Okafor", "Ben Carter", "Chloe Martin"], [(a["candidate"]["full_name"], a["screening_score"]) for a in apps]
    assert apps[0]["screening_score"] > apps[1]["screening_score"] > apps[2]["screening_score"]

    # Explainable screening detail
    ada = (await client.get(f"{API}/applications/{apps[0]['id']}", headers=h)).json()
    s = ada["screening"]
    assert {c["key"] for c in s["components"]} == {"skills", "experience", "semantic", "assessment"}
    assert abs(sum(c["contribution"] for c in s["components"]) - s["overall_score"]) < 0.2
    assert all(c["reasons"] for c in s["components"])
    assert s["requirements"] and all(r["evidence"] for r in s["requirements"])
    assert any(r["quote_verified"] for r in s["requirements"])
    assert s["blind_screening"] is True and s["redactions"].get("name", 0) >= 0
    assert s["skill_gap"]["required_coverage_pct"] == 100.0
    assert ada["experience"]["total_years"] > 8

    chloe = next(a for a in apps if a["candidate"]["full_name"] == "Chloe Martin")
    assert "Missing more than half of the required skills" in chloe["flags"]

    # Re-uploading the same file is deduplicated
    dup = await upload(client, h, job["id"], ["resume_ada_strong.txt"])
    assert not dup["created"] and len(dup["duplicates"]) == 1

    # Semantic talent search (pgvector)
    found = (await client.get(f"{API}/candidates", headers=h,
                              params={"q": "Kafka Kubernetes backend engineer", "semantic": True})).json()
    assert found["items"][0]["full_name"] == "Ada Okafor"

    # ── AI interview ──
    iv = await client.post(f"{API}/applications/{ada['id']}/interview", headers=h)
    assert iv.status_code == 200, iv.text
    interview = iv.json()
    token = interview["link"].rsplit("/", 1)[-1]
    assert len(interview["plan"]["questions"]) == 5
    assert (await client.post(f"{API}/applications/{ada['id']}/interview", headers=h)).status_code == 409

    public = (await client.get(f"{API}/public/interviews/{token}")).json()
    assert public["consent_given"] is False and public["messages"] == []
    assert (await client.post(f"{API}/public/interviews/{token}/messages", json={"message": "hi"})).status_code == 422
    assert (await client.post(f"{API}/public/interviews/{token}/start", json={"consent": False})).status_code == 422
    started = (await client.post(f"{API}/public/interviews/{token}/start", json={"consent": True})).json()
    assert started["status"] == "in_progress" and started["messages"][0]["kind"] == "greeting"

    # A short answer triggers exactly one follow-up
    r = (await client.post(f"{API}/public/interviews/{token}/messages", json={"message": "I built APIs."})).json()
    assert r["new_messages"][0]["kind"] == "follow_up" and r["answered_questions"] == 1
    long_answer = ("At Streamline Analytics I redesigned our PostgreSQL indexing strategy because p95 latency was "
                   "900ms. I measured the slow queries, decided on partial indexes and a read replica, and the "
                   "result was 120ms p95 with 35% lower cost. The trade-off was more write overhead, which we "
                   "monitored with dashboards for users across regions to validate impact at scale.")
    for _ in range(12):
        r = (await client.post(f"{API}/public/interviews/{token}/messages", json={"message": long_answer})).json()
        if r["completed"]:
            break
        # identical resubmission within the idempotency window is a no-op → vary the text
        long_answer += " Additionally, we documented the decision."
    assert r["completed"] and r["new_messages"][-1]["kind"] == "closing"
    closed = await client.post(f"{API}/public/interviews/{token}/messages", json={"message": "one more"})
    assert closed.status_code == 409

    await tasks.wait_all()
    detail = (await client.get(f"{API}/applications/{ada['id']}", headers=h)).json()
    ev = detail["evaluation"]
    assert ev["status"] == "completed", ev
    assert ev["recommendation"] in {"strong_hire", "hire", "lean_hire", "lean_no_hire", "no_hire"}
    assert {c["key"] for c in ev["components"]} == {"screening", "interview"}
    assert ev["bias_audit"]["method"] == "counterfactual_masking"
    assert ev["bias_audit"]["risk"] == "low"  # deterministic mock → zero delta
    assert detail["final_score"] == ev["composite_score"]

    # ── Stage change, dashboard, fairness, audit ──
    upd = await client.patch(f"{API}/applications/{ada['id']}", headers=h, json={"stage": "offer", "notes": "Great"})
    assert upd.json()["stage"] == "offer"

    dash = (await client.get(f"{API}/dashboard", headers=h)).json()
    assert dash["kpis"]["applications"] == 3 and dash["kpis"]["interviews_completed"] == 1
    assert sum(b["count"] for b in dash["score_distribution"]) == 3
    assert dash["top_candidates"][0]["candidate_name"] == "Ada Okafor"

    fair = (await client.get(f"{API}/fairness", headers=h)).json()
    assert fair["blind_screening"] and fair["evaluations_total"] == 1 and fair["screenings_blind"] == 3

    logs = (await client.get(f"{API}/audit-logs", headers=h)).json()
    actions = {i["action"] for i in logs["items"]}
    assert {"job.created", "applications.uploaded", "application.screened", "interview.completed",
            "evaluation.completed", "application.stage_changed"} <= actions

    interviews = (await client.get(f"{API}/interviews", headers=h)).json()
    assert interviews[0]["status"] == "completed" and interviews[0]["answered_questions"] == 5


async def test_tenant_isolation_and_rbac(client):
    a = await register(client, "Org A")
    b = await register(client, "Org B")
    job = await create_ready_job(client, a["headers"])
    up = await upload(client, a["headers"], job["id"], ["resume_ben_partial.txt"])
    app_id, cand_id = up["created"][0]["id"], up["created"][0]["candidate"]["id"]

    for path in (f"/jobs/{job['id']}", f"/applications/{app_id}", f"/candidates/{cand_id}"):
        assert (await client.get(API + path, headers=b["headers"])).status_code == 404
    assert (await client.get(f"{API}/jobs", headers=b["headers"])).json() == []
    assert (await client.get(f"{API}/candidates", headers=b["headers"])).json()["total"] == 0

    # Viewer role is read-only
    invite = await client.post(f"{API}/users", headers=a["headers"], json={
        "email": f"viewer-{uuid.uuid4().hex[:6]}@example.com", "full_name": "Val Viewer", "role": "viewer",
        "temporary_password": "Temp0rary!pw"})
    assert invite.status_code == 201
    login = await client.post(f"{API}/auth/login", json={"email": invite.json()["user"]["email"],
                                                    "password": "Temp0rary!pw"})
    vh = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert (await client.get(f"{API}/jobs", headers=vh)).status_code == 200
    denied = await client.post(f"{API}/jobs", headers=vh, json={"title": "X", "description": "y" * 60})
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "forbidden"
    assert (await client.get(f"{API}/audit-logs", headers=vh)).status_code == 403


async def test_bias_check_and_erasure(client):
    owner = await register(client)
    h = owner["headers"]
    report = (await client.post(f"{API}/jobs/bias-check", headers=h, json={
        "description": "Looking for a young rockstar developer. He must be a native English speaker."})).json()
    assert report["rating"] == "biased" and len(report["flags"]) >= 3

    job = await create_ready_job(client, h)
    up = await upload(client, h, job["id"], ["resume_chloe_weak.txt"])
    cand_id = up["created"][0]["candidate"]["id"]
    async with SessionLocal() as db:
        before = await db.scalar(select(func.count()).where(Embedding.owner_id == uuid.UUID(cand_id)))
    assert before and before > 0

    assert (await client.delete(f"{API}/candidates/{cand_id}", headers=h)).status_code == 204
    assert (await client.get(f"{API}/candidates/{cand_id}", headers=h)).status_code == 404
    async with SessionLocal() as db:
        after = await db.scalar(select(func.count()).where(Embedding.owner_id == uuid.UUID(cand_id)))
    assert after == 0
    assert (await client.get(f"{API}/jobs/{job['id']}/applications", headers=h)).json() == []


async def test_tiers_criteria_and_dashboard_period(client):
    owner = await register(client)
    h = owner["headers"]
    job = await create_ready_job(client, h)
    await upload(client, h, job["id"], ["resume_ada_strong.txt", "resume_ben_partial.txt", "resume_chloe_weak.txt"])

    job = (await client.get(f"{API}/jobs/{job['id']}", headers=h)).json()
    c = job["counts"]
    assert c["strong"] + c["review"] + c["low"] == c["screened"] == 3

    apps = (await client.get(f"{API}/jobs/{job['id']}/applications", headers=h)).json()
    ada = apps[0]
    assert ada["tier"] == "strong" and ada["one_liner"]
    assert ada["candidate"]["current_company"] == "Streamline Analytics"
    assert ada["skill_chips"] and {"skill", "status", "importance"} <= set(ada["skill_chips"][0])
    chloe = next(a for a in apps if a["candidate"]["full_name"] == "Chloe Martin")
    assert chloe["tier"] == "low" and chloe["skill_chips"][0]["status"] == "missing"  # missing must-haves first

    strong = (await client.get(f"{API}/jobs/{job['id']}/applications", headers=h, params={"tier": "strong"})).json()
    assert [a["id"] for a in strong] == [a["id"] for a in apps if a["tier"] == "strong"]

    detail = (await client.get(f"{API}/applications/{ada['id']}", headers=h)).json()
    assert detail["raw_text"].startswith("Ada Okafor") and detail["filename"] == "resume_ada_strong.txt"
    assert detail["screened_at"]

    # Editing criteria re-scores everyone against the new must-haves
    r = await client.patch(f"{API}/jobs/{job['id']}", headers=h, json={
        "criteria": {"required_skills": ["Marketing", "SEO"], "nice_to_have_skills": ["Excel"], "min_years_experience": 2}})
    assert r.status_code == 200, r.text
    assert r.json()["extracted"]["required_skills"] == ["Marketing", "SEO"]
    await tasks.wait_all()
    rescored = (await client.get(f"{API}/jobs/{job['id']}/applications", headers=h)).json()
    assert rescored[0]["candidate"]["full_name"] == "Chloe Martin"

    # Stage change feeds the dashboard's shortlisted metric; period metrics are populated
    await client.patch(f"{API}/applications/{ada['id']}", headers=h, json={"stage": "shortlisted"})
    dash = (await client.get(f"{API}/dashboard", headers=h, params={"days": 7})).json()
    p = dash["period"]
    assert p["days"] == 7 and p["screened"]["value"] >= 3 and p["shortlisted"]["value"] == 1
    assert p["avg_seconds_to_screen"]["value"] is not None and p["screened"]["previous"] == 0
    assert dash["needs_review_total"] == len([a for a in rescored if a["tier"] == "review" and a["stage"] == "new"])
    detail = (await client.get(f"{API}/applications/{ada['id']}", headers=h)).json()
    assert detail["stage_changed_by"] == "Owner Person"
    await tasks.wait_all()  # the shortlist invitation runs in the background


async def test_shortlist_emails_interview_invitation(client, monkeypatch):
    sent: list[dict] = []

    async def fake_send(**kwargs) -> str:
        sent.append(kwargs)
        return "smtp"

    monkeypatch.setattr("app.services.email.send_email", fake_send)
    owner = await register(client, org="Invite Co")
    h = owner["headers"]
    job = await create_ready_job(client, h)
    await upload(client, h, job["id"], ["resume_ada_strong.txt", "resume_ben_partial.txt"])
    ada, ben = (await client.get(f"{API}/jobs/{job['id']}/applications", headers=h)).json()

    r = await client.patch(f"{API}/applications/{ada['id']}", headers=h, json={"stage": "shortlisted"})
    assert r.status_code == 200 and r.json()["interview"] is None  # generated in the background
    await tasks.wait_all()

    assert len(sent) == 1 and sent[0]["to"] == "ada.okafor@example.com"
    assert "Congratulations" in sent[0]["subject"] and "shortlisted" in sent[0]["text"]
    token = sent[0]["text"].split("/interview/")[1].split()[0]
    assert f"/interview/{token}" in sent[0]["html"]
    public = await client.get(f"{API}/public/interviews/{token}")
    assert public.status_code == 200 and public.json()["organization_name"] == "Invite Co"

    detail = (await client.get(f"{API}/applications/{ada['id']}", headers=h)).json()
    assert detail["stage"] == "shortlisted" and detail["interview"]["status"] == "pending"
    actions = [a["action"] for a in (await client.get(f"{API}/audit-logs", headers=h)).json()["items"]]
    assert "interview.invite_sent" in actions

    # Shortlisting again before the candidate starts re-sends the same, still-working link
    await client.patch(f"{API}/applications/{ada['id']}", headers=h, json={"stage": "new"})
    await client.patch(f"{API}/applications/{ada['id']}", headers=h, json={"stage": "shortlisted"})
    await tasks.wait_all()
    assert len(sent) == 2 and f"/interview/{token}" in sent[1]["text"]
    assert (await client.get(f"{API}/public/interviews/{token}")).status_code == 200

    # Workspaces can turn the automation off
    org = owner["session"]["organization"]
    off = await client.patch(f"{API}/organization", headers=h,
                             json={"settings": {**org["settings"], "auto_invite_on_shortlist": False}})
    assert off.status_code == 200, off.text
    await client.patch(f"{API}/applications/{ben['id']}", headers=h, json={"stage": "shortlisted"})
    await tasks.wait_all()
    assert len(sent) == 2


async def test_criteria_validation(client):
    owner = await register(client)
    job = await create_ready_job(client, owner["headers"])
    bad = await client.patch(f"{API}/jobs/{job['id']}", headers=owner["headers"],
                             json={"criteria": {"required_skills": ["Python"], "min_years_experience": 99}})
    assert bad.status_code == 422


@pytest.fixture
def outbox(monkeypatch) -> list[dict]:
    """Capture every outgoing email instead of sending it."""
    sent: list[dict] = []

    async def fake_send(**kwargs) -> str:
        sent.append(kwargs)
        return "smtp"

    monkeypatch.setattr("app.services.email.send_email", fake_send)
    return sent


async def _finish_interview(client, token: str) -> None:
    await client.post(f"{API}/public/interviews/{token}/start", json={"consent": True})
    answer = ("At my last company I redesigned our PostgreSQL indexing strategy because p95 latency was 900ms. "
              "I measured the slow queries, chose partial indexes and a read replica, and cut p95 to 120ms with "
              "35% lower cost. The trade-off was write overhead, which we monitored with dashboards.")
    for i in range(14):
        r = (await client.post(f"{API}/public/interviews/{token}/messages", json={"message": f"{answer} ({i})"})).json()
        if r["completed"]:
            return
    raise AssertionError("interview did not complete")


async def test_careers_page_and_apply(client, outbox):
    owner = await register(client, org="Careers Co")
    h = owner["headers"]
    slug = owner["session"]["organization"]["slug"]
    job = await create_ready_job(client, h)

    page = (await client.get(f"{API}/public/careers/{slug}")).json()
    assert page["organization_name"] == "Careers Co" and [j["id"] for j in page["jobs"]] == [job["id"]]
    detail = (await client.get(f"{API}/public/careers/{slug}/jobs/{job['id']}")).json()
    assert detail["description"].startswith(read_sample("job_senior_backend.txt")[:40])

    def form(**over):
        data = {"full_name": "Mei Applicant", "email": "Mei.Applicant@Example.com", "consent": "true", **over}
        files = {"resume": ("mei.txt", read_sample("resume_mei_strong.txt").encode(), "text/plain")}
        return {"data": data, "files": files}

    url = f"{API}/public/careers/{slug}/jobs/{job['id']}/apply"
    assert (await client.post(url, **form(consent="false"))).status_code == 422
    assert (await client.post(url, **form(email="not-an-email"))).status_code == 422
    assert (await client.post(url, **form(website="http://spam.example"))).status_code == 201  # honeypot
    assert (await client.get(f"{API}/jobs/{job['id']}/applications", headers=h)).json() == []

    r = await client.post(url, **form())
    assert r.status_code == 201, r.text
    await tasks.wait_all()
    apps = (await client.get(f"{API}/jobs/{job['id']}/applications", headers=h)).json()
    assert len(apps) == 1 and apps[0]["source"] == "careers" and apps[0]["status"] == "completed"
    # The applicant's own details win over the parsed resume
    assert apps[0]["candidate"]["full_name"] == "Mei Applicant"
    assert apps[0]["candidate"]["email"] == "mei.applicant@example.com"
    assert [m["to"] for m in outbox] == ["mei.applicant@example.com"]
    assert "received your application" in outbox[0]["subject"]

    # Applying twice is accepted silently but creates nothing new
    assert (await client.post(url, **form())).status_code == 201
    await tasks.wait_all()
    assert len((await client.get(f"{API}/jobs/{job['id']}/applications", headers=h)).json()) == 1

    # Closed jobs and disabled careers pages aren't reachable
    await client.patch(f"{API}/jobs/{job['id']}", headers=h, json={"status": "closed"})
    assert (await client.get(f"{API}/public/careers/{slug}/jobs/{job['id']}")).status_code == 404
    org = owner["session"]["organization"]
    await client.patch(f"{API}/organization", headers=h,
                       json={"settings": {**org["settings"], "careers_page_enabled": False}})
    assert (await client.get(f"{API}/public/careers/{slug}")).status_code == 404


async def test_rejection_reminder_and_completion_emails(client, outbox, monkeypatch):
    from app.core.config import settings
    from app.models import InterviewSession
    from app.services.notifications import send_due_rejections, send_due_reminders

    owner = await register(client, org="Notify Co")
    h = owner["headers"]
    slug = owner["session"]["organization"]["slug"]
    job = await create_ready_job(client, h)
    await upload(client, h, job["id"], ["resume_ada_strong.txt", "resume_ben_partial.txt"])
    await client.post(f"{API}/public/careers/{slug}/jobs/{job['id']}/apply", data={
        "full_name": "Chloe Martin", "email": "chloe.applies@example.com", "consent": "true"},
        files={"resume": ("chloe.txt", read_sample("resume_chloe_weak.txt").encode(), "text/plain")})
    await tasks.wait_all()
    apps = {a["candidate"]["full_name"]: a for a in
            (await client.get(f"{API}/jobs/{job['id']}/applications", headers=h)).json()}
    outbox.clear()

    # ── Rejections: only after the grace period, only to applicants / interviewees, never twice ──
    for name in ("Chloe Martin", "Ben Carter"):
        await client.patch(f"{API}/applications/{apps[name]['id']}", headers=h, json={"stage": "rejected"})
    assert await send_due_rejections() == 0  # still inside the undo window
    monkeypatch.setattr(settings, "rejection_email_delay_minutes", 0)
    assert await send_due_rejections() == 1
    assert [m["to"] for m in outbox] == ["chloe.applies@example.com"]  # Ben was sourced, never contacted
    assert "Your application for" in outbox[0]["subject"]
    await client.patch(f"{API}/applications/{apps['Chloe Martin']['id']}", headers=h, json={"stage": "new"})
    await client.patch(f"{API}/applications/{apps['Chloe Martin']['id']}", headers=h, json={"stage": "rejected"})
    assert await send_due_rejections() == 0
    outbox.clear()

    # ── Shortlist invite, then an expiry reminder repeating the same link ──
    ada = apps["Ada Okafor"]
    await client.patch(f"{API}/applications/{ada['id']}", headers=h, json={"stage": "shortlisted"})
    await tasks.wait_all()
    token = outbox[0]["text"].split("/interview/")[1].split()[0]
    assert await send_due_reminders() == 0  # not close to expiry yet
    async with SessionLocal() as db:
        session = await db.scalar(select(InterviewSession)
                                  .where(InterviewSession.application_id == uuid.UUID(ada["id"])))
        session.created_at = datetime.now(UTC) - timedelta(days=12)
        session.expires_at = datetime.now(UTC) + timedelta(hours=20)
        await db.commit()
    assert await send_due_reminders() == 1
    assert await send_due_reminders() == 0
    assert "Reminder" in outbox[1]["subject"] and f"/interview/{token}" in outbox[1]["text"]
    outbox.clear()

    # ── Recruiter alert once the finished interview is evaluated ──
    await _finish_interview(client, token)
    await tasks.wait_all()
    alerts = [m for m in outbox if "completed their AI interview" in m["subject"]]
    assert [m["to"] for m in alerts] == [owner["email"]]
    assert "final score" in alerts[0]["text"]
    await client.post(f"{API}/applications/{ada['id']}/evaluation", headers=h)  # a re-run doesn't re-alert
    await tasks.wait_all()
    assert len([m for m in outbox if "completed their AI interview" in m["subject"]]) == 1


async def test_password_reset_and_email_invites(client, outbox):
    owner = await register(client, org="Accounts Co")

    assert (await client.post(f"{API}/auth/forgot-password", json={"email": "nobody@example.com"})).status_code == 204
    assert (await client.post(f"{API}/auth/forgot-password", json={"email": owner["email"]})).status_code == 204
    await tasks.wait_all()
    assert [m["to"] for m in outbox] == [owner["email"]]
    token = outbox[0]["text"].split("token=")[1].split()[0]

    weak = await client.post(f"{API}/auth/reset-password", json={"token": token, "password": "short"})
    assert weak.status_code == 422
    ok = await client.post(f"{API}/auth/reset-password", json={"token": token, "password": "N3w-passw0rd"})
    assert ok.status_code == 204
    again = await client.post(f"{API}/auth/reset-password", json={"token": token, "password": "An0ther-pass"})
    assert again.status_code == 422  # single use
    login = await client.post(f"{API}/auth/login", json={"email": owner["email"], "password": "N3w-passw0rd"})
    assert login.status_code == 200
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}
    outbox.clear()

    # Email invitation: no password from the admin; the teammate picks their own
    email = f"rita-{uuid.uuid4().hex[:6]}@example.com"
    r = await client.post(f"{API}/users", headers=h, json={"email": email, "full_name": "Rita Recruiter",
                                                           "role": "recruiter"})
    assert r.status_code == 201, r.text
    result = r.json()
    assert result["user"]["invite_pending"] is True and result["invite_emailed"] is True
    assert [m["to"] for m in outbox] == [email] and "invited you to join Accounts Co" in outbox[0]["subject"]
    first = result["invite_link"].split("token=")[1]

    resent = (await client.post(f"{API}/users/{result['user']['id']}/resend-invite", headers=h)).json()
    second = resent["invite_link"].split("token=")[1]
    assert (await client.get(f"{API}/auth/invitations/{first}")).status_code == 422  # superseded
    preview = (await client.get(f"{API}/auth/invitations/{second}")).json()
    assert preview == {"email": email, "full_name": "Rita Recruiter", "organization_name": "Accounts Co"}

    client.cookies.clear()
    accepted = await client.post(f"{API}/auth/accept-invite", json={"token": second, "password": "Rita-pass1"})
    assert accepted.status_code == 200 and accepted.json()["user"]["role"] == "recruiter"
    client.cookies.clear()
    users = (await client.get(f"{API}/users", headers=h)).json()
    assert next(u for u in users if u["email"] == email)["invite_pending"] is False
    assert (await client.post(f"{API}/users/{result['user']['id']}/resend-invite", headers=h)).status_code == 422
