# ScreenIQ 2.0 — AI Resume Screening & Interview Platform

Multi-tenant SaaS that screens resumes with explainable, evidence-backed scores, runs tailored AI
interviews, and audits every hiring decision for bias.

```
Resume → Parser → Skill Extraction → Experience Analysis → JD Matching (RAG) → Candidate Score
       → AI Interview → Final Evaluation (LLM-as-a-judge + counterfactual bias audit)
```

## Features

| Capability | How it works |
|---|---|
| **Resume parsing** | PDF (pdfplumber), DOCX (paragraphs + tables), TXT. Magic-byte checks, size limits, scanned-PDF detection. Claude structured outputs extract roles, dates, skills, education. |
| **Skill extraction** | LLM extraction + a 200-entry taxonomy for canonicalization (`k8s` → Kubernetes) and in-text detection. |
| **Experience analysis** | Deterministic: union of dated role intervals (overlaps aren't double-counted), tenure, gaps, seniority, progression. |
| **Semantic matching** | Embeddings (local BGE-large, OpenAI, or a hashing demo embedder) stored in **pgvector**; section-vs-JD similarity with per-provider calibration. |
| **RAG** | Each JD requirement retrieves its top-k resume chunks from pgvector; Claude judges the evidence and must quote it; quotes are **verified** against the resume. |
| **Skill-gap analysis** | exact → alias → in-text mention → embedding similarity → related token, with the method shown per skill. |
| **Explainable scoring** | 4 weighted components (skills, experience, semantic, AI assessment), each with plain-language reasons; per-job or org-level weights. |
| **AI-generated questions** | Gap-aware, structured plan (deep-dive, technical, gap-probe, behavioral). |
| **AI interview chatbot** | Tokenized candidate link, consent screen, follow-ups, resumable, idempotent submits, mobile-friendly. |
| **Final evaluation** | LLM-as-a-judge rubric per criterion with evidence quotes; composite = screening × w + interview × w. |
| **Bias detection** | Blind screening (PII & demographic-proxy redaction), inclusive-language analysis of JDs, counterfactual masked-vs-unmasked grading, gaps never scored, prompt-injection flags. |
| **Recruiter dashboard** | Period KPIs with deltas, active roles with Strong / Needs review / Low fit pipelines, a review queue, ranked candidate tables with bulk actions, talent pool with semantic search, fairness center, audit log. |
| **Editable criteria** | Must-have / nice-to-have skills and minimum years are drafted by the AI and editable by recruiters; saving re-scores every candidate. |
| **SaaS foundations** | Orgs & users, roles (owner/admin/recruiter/viewer), JWT in httpOnly cookie, tenant isolation, rate limiting, audit trail, GDPR erasure, structured logging, request IDs. |

## Architecture

- **backend/** — FastAPI (async), SQLAlchemy 2 + asyncpg, Alembic, pgvector, Anthropic SDK.
  - `app/llm/` — one gateway to Claude (`claude-opus-5` by default): structured outputs, adaptive thinking, per-task effort, refusal handling with server-side fallbacks. `mock.py` is an offline heuristic provider for demos/CI (refused in production).
  - `app/services/` — parsing, chunking, embeddings, retrieval, skill gap, experience, scoring, screening, interviews, evaluation, fairness, pipeline.
  - Long-running AI work runs as background tasks with progress persisted on rows; a sweeper marks stale work retryable.
- **frontend/** — React 19, Vite, Tailwind 4, TanStack Query. Light/dark themes, code-split routes.

## Quick start (Docker)

```bash
cp .env.example .env        # set ANTHROPIC_API_KEY and SECRET_KEY
docker compose up --build
```

Open http://localhost:8080 and create a workspace. The first build downloads the BGE model (~1.3 GB).
For a smaller image use `EMBEDDING_PROVIDER=openai` with `INSTALL_ML=false`.

**No API key?** Set `LLM_PROVIDER=mock` and `EMBEDDING_PROVIDER=hash` for a fully offline demo
(output is simulated — a banner says so in the app).

## Local development

```bash
# Postgres with pgvector
docker run -d --name screeniq-db -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=screeniq -p 5432:5432 pgvector/pgvector:pg16

# Backend
cd backend
python -m venv .venv && .venv/Scripts/activate   # or: source .venv/bin/activate
pip install -r requirements-dev.txt              # + requirements-ml.txt for local BGE embeddings
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/screeniq
export LLM_PROVIDER=mock EMBEDDING_PROVIDER=hash # or ANTHROPIC_API_KEY=... for real Claude
alembic upgrade head
python -m scripts.seed_demo                      # optional demo workspace (credentials in the script)
uvicorn app.main:app --reload

# Frontend (proxies /api to :8000)
cd frontend && npm install && npm run dev        # http://localhost:5173
```

API docs: http://localhost:8000/docs (disabled in production).

## Tests

```bash
cd backend
ruff check app tests scripts
pytest                                   # unit tests
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/screeniq_test pytest   # + end-to-end API tests
cd ../frontend && npm run lint && npm run build
```

The end-to-end suite covers auth, JD extraction, upload → RAG screening → ranking, the AI interview over
the public link, evaluation with bias audit, tenant isolation, RBAC and right-to-erasure.

## Production checklist

- `ENVIRONMENT=production` (the app refuses to start with a default `SECRET_KEY`, the mock LLM or hash embeddings).
- Serve over HTTPS (session cookies become `Secure` automatically).
- Set `FRONTEND_URL` to your public URL (used in candidate interview links) and `CORS_ORIGINS` if the API is on another origin.
- Back up the Postgres volume; tune `MAX_CONCURRENT_PIPELINES` to your LLM rate limits.
- The in-process rate limiter and task runner are per instance; when scaling out, add a shared limiter at the ingress and move `app/services/tasks.spawn` to a queue (arq/Celery).

## Responsible use

AI output is decision support. Scores include reasons and evidence, candidates consent before AI
interviews, identity is masked for AI assessment by default, and hiring decisions stay with people.
Check local regulations (e.g. NYC Local Law 144, EU AI Act) before use in hiring.
