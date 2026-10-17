"""
Hybrid skill-gap analysis: lexical + taxonomy + in-text evidence + embeddings.

For every JD skill, the first rule that fires wins:
  1. exact      — same normalised name                      → matched
  2. alias      — same canonical taxonomy entry             → matched  ("k8s" ≈ "Kubernetes")
  3. mentioned  — appears in the resume text, not the list  → matched
  4. semantic   — embedding similarity ≥ match threshold    → matched  ("Postgres tuning" ≈ "PostgreSQL")
                  ≥ partial threshold                       → partial
  5. related    — shares a significant token                → partial  ("AWS" vs "AWS Lambda")
  otherwise                                                 → missing
"""

from app.schemas.screening import SkillGapResult, SkillMatch
from app.services.embeddings import Embedder, cosine
from app.services.skills import canonicalize, mentioned_in, normalize_key, tokens

_GENERIC_TOKENS = {"development", "experience", "design", "management", "engineering", "systems", "skills",
                   "data", "software", "web", "services", "tools", "apis", "api", "cloud", "testing"}


async def compute_skill_gap(
    required_skills: list[str],
    nice_to_have_skills: list[str],
    candidate_skills: list[str],
    resume_text: str,
    embedder: Embedder,
) -> SkillGapResult:
    jd_items = [(s, "required") for s in required_skills] + [(s, "nice_to_have") for s in nice_to_have_skills]
    cand_norm = {normalize_key(s): s for s in candidate_skills}
    cand_canon = {canonicalize(s).lower(): s for s in candidate_skills}

    matches: dict[int, SkillMatch] = {}
    pending: list[int] = []
    for i, (skill, importance) in enumerate(jd_items):
        key = normalize_key(skill)
        canon = canonicalize(skill).lower()
        if key in cand_norm:
            matches[i] = SkillMatch(skill=skill, importance=importance, status="matched", method="exact",
                                    matched_to=cand_norm[key])
        elif canon in cand_canon:
            matches[i] = SkillMatch(skill=skill, importance=importance, status="matched", method="alias",
                                    matched_to=cand_canon[canon])
        elif mentioned_in(resume_text, skill):
            matches[i] = SkillMatch(skill=skill, importance=importance, status="matched", method="mentioned")
        else:
            pending.append(i)

    # Semantic pass for everything still unmatched (one batched embedding call each side)
    if pending and candidate_skills:
        jd_vecs = await embedder.embed_documents([jd_items[i][0] for i in pending])
        cand_vecs = await embedder.embed_documents(candidate_skills)
        cal = embedder.calibration
        for i, vec in zip(pending, jd_vecs, strict=True):
            best_sim, best_skill = max(
                ((cosine(vec, cv), cs) for cv, cs in zip(cand_vecs, candidate_skills, strict=True)),
                key=lambda t: t[0],
            )
            skill, importance = jd_items[i]
            if best_sim >= cal.skill_match:
                matches[i] = SkillMatch(skill=skill, importance=importance, status="matched", method="semantic",
                                        matched_to=best_skill, similarity=round(best_sim, 3))
            elif best_sim >= cal.skill_partial:
                matches[i] = SkillMatch(skill=skill, importance=importance, status="partial", method="semantic",
                                        matched_to=best_skill, similarity=round(best_sim, 3))

    for i in pending:
        if i in matches:
            continue
        skill, importance = jd_items[i]
        jd_tokens = tokens(skill) - _GENERIC_TOKENS
        related = next(
            (cs for cs in candidate_skills if jd_tokens and (jd_tokens & (tokens(cs) - _GENERIC_TOKENS))),
            None,
        )
        if related:
            matches[i] = SkillMatch(skill=skill, importance=importance, status="partial", method="related",
                                    matched_to=related)
        else:
            matches[i] = SkillMatch(skill=skill, importance=importance, status="missing", method="none")

    ordered = [matches[i] for i in range(len(jd_items))]
    req = [m for m in ordered if m.importance == "required"]
    nice = [m for m in ordered if m.importance == "nice_to_have"]

    def coverage(items: list[SkillMatch]) -> float:
        if not items:
            return 0.0
        points = sum(1.0 if m.status == "matched" else 0.5 if m.status == "partial" else 0.0 for m in items)
        return round(points / len(items) * 100, 1)

    used = {normalize_key(m.matched_to) for m in ordered if m.matched_to}
    jd_canon = {canonicalize(s).lower() for s, _ in jd_items}
    bonus = [
        s for s in candidate_skills
        if normalize_key(s) not in used and canonicalize(s).lower() not in jd_canon
    ]

    return SkillGapResult(
        matches=ordered,
        matched_required=[m.skill for m in req if m.status == "matched"],
        partial_required=[m.skill for m in req if m.status == "partial"],
        missing_required=[m.skill for m in req if m.status == "missing"],
        matched_nice_to_have=[m.skill for m in nice if m.status != "missing"],
        missing_nice_to_have=[m.skill for m in nice if m.status == "missing"],
        bonus_skills=bonus[:40],
        required_coverage_pct=coverage(req),
        nice_to_have_coverage_pct=coverage(nice),
    )
