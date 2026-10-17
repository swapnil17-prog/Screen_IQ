"""
Explainable scoring. Pure functions: inputs in, (score 0-100, reasons) out.

Final screening score = Σ weight_i × component_i over:
  skills      — required / nice-to-have coverage from the hybrid skill-gap engine
  experience  — years vs requirement, role relevance, seniority alignment
  semantic    — calibrated embedding similarity of resume sections to the JD
  assessment  — LLM judgement over retrieved evidence, per requirement

Employment gaps are deliberately *not* scored: they correlate with caregiving,
illness and disability and are a known source of disparate impact.
"""

from app.schemas.extraction import JDExtraction
from app.schemas.screening import (
    ExperienceAnalysis,
    ExperienceFit,
    RelevantRole,
    RequirementAssessment,
    ScoreComponent,
    SemanticMatch,
    SemanticSection,
    SkillGapResult,
)
from app.services.embeddings import Calibration
from app.services.experience import SENIORITY_RANK

COMPONENT_LABELS = {
    "skills": "Skills match",
    "experience": "Experience fit",
    "semantic": "Semantic similarity",
    "assessment": "AI evidence assessment",
}

SECTION_WEIGHTS = {"experience": 0.45, "skills": 0.30, "summary": 0.15, "education": 0.10}


# Recruiter triage tiers shown throughout the UI
TIER_STRONG = 80.0
TIER_REVIEW = 60.0


def tier_for(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= TIER_STRONG:
        return "strong"
    if score >= TIER_REVIEW:
        return "review"
    return "low"


def label_for(score: float) -> str:
    if score >= 80:
        return "strong_match"
    if score >= 65:
        return "good_match"
    if score >= 50:
        return "potential"
    return "weak_match"


def _join(items: list[str], limit: int = 5) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f" +{len(items) - limit} more" if len(items) > limit else "")


def skills_component(gap: SkillGapResult) -> tuple[float, list[str]]:
    req = [m for m in gap.matches if m.importance == "required"]
    nice = [m for m in gap.matches if m.importance == "nice_to_have"]
    reasons: list[str] = []

    if req and nice:
        score = 0.8 * gap.required_coverage_pct + 0.2 * gap.nice_to_have_coverage_pct
    elif req:
        score = gap.required_coverage_pct
    elif nice:
        score = gap.nice_to_have_coverage_pct
        reasons.append("The job lists no explicit must-have skills; scored on preferred skills only.")
    else:
        return 50.0, ["The job description lists no specific skills, so this component is neutral."]

    if req:
        matched = sum(1 for m in req if m.status == "matched")
        partial = sum(1 for m in req if m.status == "partial")
        reasons.append(
            f"Matched {matched} of {len(req)} required skills"
            + (f" (+{partial} partial)" if partial else "")
            + f" — {gap.required_coverage_pct:.0f}% coverage."
        )
    if gap.missing_required:
        reasons.append(f"Missing required: {_join(gap.missing_required)}.")
    semantic = [m for m in gap.matches if m.method == "semantic" and m.status == "matched"]
    if semantic:
        reasons.append(
            "Semantic matches: " + "; ".join(f"“{m.skill}” ≈ “{m.matched_to}”" for m in semantic[:3]) + "."
        )
    mentioned = [m.skill for m in gap.matches if m.method == "mentioned"]
    if mentioned:
        reasons.append(f"Found in experience text (not in skills list): {_join(mentioned, 4)}.")
    if nice:
        reasons.append(
            f"Nice-to-have: {len(gap.matched_nice_to_have)} of {len(nice)} "
            f"({gap.nice_to_have_coverage_pct:.0f}%)."
        )
    return round(score, 1), reasons


def _seniority_alignment(expected: str | None, estimated: str | None) -> tuple[float | None, str | None]:
    if not expected or not estimated or expected not in SENIORITY_RANK or estimated not in SENIORITY_RANK:
        return None, None
    diff = SENIORITY_RANK[estimated] - SENIORITY_RANK[expected]
    if diff == 0:
        return 100.0, f"Seniority aligns with the role ({expected})."
    if diff > 0:
        score = 90.0 if diff == 1 else 75.0
        return score, f"Estimated seniority ({estimated}) is above the role level ({expected})."
    score = {-1: 70.0, -2: 45.0}.get(diff, 25.0)
    return score, f"Estimated seniority ({estimated}) is below the role level ({expected})."


def experience_component(
    jd: JDExtraction,
    analysis: ExperienceAnalysis,
    relevant_roles: list[RelevantRole],
) -> tuple[float, list[str], ExperienceFit]:
    parts: list[tuple[float, float]] = []  # (score, weight)
    reasons: list[str] = []
    years = analysis.total_years
    required = jd.min_years_experience

    if required:
        if years is None:
            parts.append((40.0, 0.5))
            reasons.append(f"Role asks for {required:g}+ years; experience duration couldn't be determined.")
        else:
            ratio = years / required
            years_score = 100.0 if ratio >= 1 else round(100 * ratio**1.2, 1)
            parts.append((years_score, 0.5))
            verdict = "meets" if ratio >= 1 else "is below"
            reasons.append(f"{years:g} years of experience {verdict} the {required:g}+ years required.")
    elif years is not None:
        reasons.append(f"{years:g} years of total experience (no minimum stated).")

    if relevant_roles:
        top = sorted((r.relevance for r in relevant_roles), reverse=True)
        relevance = top[0] if len(top) == 1 else 0.7 * top[0] + 0.3 * top[1]
        parts.append((relevance, 0.3))
        best = max(relevant_roles, key=lambda r: r.relevance)
        reasons.append(f"Most relevant role: {best.title} at {best.company} ({best.relevance:.0f}% relevance).")

    alignment, why = _seniority_alignment(jd.seniority, analysis.seniority_estimate)
    if alignment is not None and why:
        parts.append((alignment, 0.2))
        reasons.append(why)

    if analysis.gaps:
        reasons.append("Employment gaps are shown for context only and never affect the score.")

    fit = ExperienceFit(
        candidate_years=years,
        required_years=required,
        expected_seniority=jd.seniority,
        estimated_seniority=analysis.seniority_estimate,
        relevant_roles=sorted(relevant_roles, key=lambda r: r.relevance, reverse=True)[:5],
    )
    if not parts:
        return 50.0, reasons or ["Not enough experience information to assess; component is neutral."], fit
    total_weight = sum(w for _, w in parts)
    score = sum(s * w for s, w in parts) / total_weight
    return round(score, 1), reasons, fit


def semantic_component(
    section_sims: dict[str, float], calibration: Calibration
) -> tuple[float, list[str], SemanticMatch]:
    sections = [
        SemanticSection(section=name, similarity=round(sim, 4), calibrated=calibration.to_score(sim))
        for name, sim in section_sims.items()
    ]
    weighted = [(s.calibrated, SECTION_WEIGHTS.get(s.section, 0.1)) for s in sections]
    if not weighted:
        return 50.0, ["No resume sections could be embedded; component is neutral."], SemanticMatch(score=50.0)
    score = round(sum(c * w for c, w in weighted) / sum(w for _, w in weighted), 1)
    best = max(sections, key=lambda s: s.calibrated)
    reasons = [
        f"Resume content is {score:.0f}% semantically aligned with the job description.",
        f"Strongest section: {best.section} ({best.calibrated:.0f}%).",
    ]
    return score, reasons, SemanticMatch(score=score, sections=sorted(sections, key=lambda s: -s.calibrated))


def assessment_component(fit_score: float, requirements: list[RequirementAssessment]) -> tuple[float, list[str]]:
    fit = max(0.0, min(100.0, float(fit_score)))
    reasons = [f"AI holistic fit judgement: {fit:.0f}/100."]
    if not requirements:
        return round(fit, 1), reasons
    points = {"met": 1.0, "partial": 0.5, "not_met": 0.0}
    weights = [2.0 if r.importance == "required" else 1.0 for r in requirements]
    req_score = sum(points[r.verdict] * w for r, w in zip(requirements, weights, strict=True)) / sum(weights) * 100
    met = sum(1 for r in requirements if r.verdict == "met")
    partial = sum(1 for r in requirements if r.verdict == "partial")
    reasons.append(
        f"{met} of {len(requirements)} requirements met, {partial} partially met, backed by retrieved resume evidence."
    )
    verified = sum(1 for r in requirements if r.evidence_quote and r.quote_verified)
    quoted = sum(1 for r in requirements if r.evidence_quote)
    if quoted:
        reasons.append(f"{verified} of {quoted} cited quotes verified against the resume text.")
    return round(0.5 * fit + 0.5 * req_score, 1), reasons


def combine(
    raw: dict[str, tuple[float, list[str]]], weights: dict[str, float]
) -> tuple[list[ScoreComponent], float]:
    total = sum(weights.get(k, 0.0) for k in raw) or 1.0
    components = []
    for key, (score, reasons) in raw.items():
        weight = weights.get(key, 0.0) / total
        components.append(
            ScoreComponent(
                key=key,  # type: ignore[arg-type]
                label=COMPONENT_LABELS[key],
                score=round(score, 1),
                weight=round(weight, 4),
                contribution=round(score * weight, 2),
                reasons=reasons,
            )
        )
    overall = round(sum(c.contribution for c in components), 1)
    return components, max(0.0, min(100.0, overall))


def confidence_for(
    *,
    has_dated_experience: bool,
    skill_count: int,
    requirement_count: int,
    evidence_count: int,
    quotes_verified_ratio: float | None,
) -> str:
    points = 0
    points += 1 if has_dated_experience else 0
    points += 1 if skill_count >= 5 else 0
    points += 1 if requirement_count >= 3 else 0
    points += 1 if evidence_count >= 4 else 0
    points += 1 if quotes_verified_ratio is None or quotes_verified_ratio >= 0.6 else 0
    return "high" if points >= 5 else "medium" if points >= 3 else "low"
