"""
Deterministic, dependency-free stand-in for the LLM (LLM_PROVIDER=mock).

It answers each structured task with transparent heuristics computed from the
`context` the caller passes, so the full product — upload, screening, interview,
evaluation — works offline for demos, local development and CI. Outputs are
plausible but simplistic; never use this provider for real hiring decisions
(config validation refuses it in production).
"""

import re
from typing import Any, TypeVar

from pydantic import BaseModel

from app.schemas.evaluation import CriterionScore, InterviewRubricLLM, QuestionScore
from app.schemas.extraction import EducationEntry, JDExtraction, ResumeExtraction, WorkEntry
from app.schemas.interview import InterviewPlanLLM, InterviewQuestion, TurnDecision
from app.schemas.screening import LLMRequirementVerdict, ScreeningAssessmentLLM
from app.services.experience import seniority_from_title
from app.services.skills import find_skills_in_text, mentioned_in

T = TypeVar("T", bound=BaseModel)

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\+?\(?\d[\d\s().-]{8,}\d")
_DATE = r"(?:[A-Za-z]{3,9}\.?\s+)?\d{4}|\d{1,2}/\d{4}"
_RANGE = re.compile(rf"(?P<start>{_DATE})\s*(?:-|–|—|to)\s*(?P<end>{_DATE}|present|current|now)", re.I)
_BULLET = re.compile(r"^\s*(?:[•●▪◦*·-]|\d+[.)])\s+")
_HEADER = re.compile(
    r"^(summary|profile|about|objective|experience|work experience|professional experience|employment"
    r"|skills|technical skills|core skills|education|certifications?|projects|languages|interests)\s*:?\s*$",
    re.I,
)
_DEGREE = re.compile(r"\b(b\.?s\.?c?|b\.?a\.?|bachelor|m\.?s\.?c?|master|mba|ph\.?d|doctorate|b\.?tech|m\.?tech|"
                     r"b\.?e\.?|associate degree|diploma)\b", re.I)
_INSTITUTION = re.compile(r"[A-Z][\w.&' -]*(?:University|College|Institute|School|Academy)[\w.&' -]*"
                          r"|(?:University|Institute) of [A-Z][\w .&'-]+")


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9+#]+", text.lower())


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _clip_words(text: str, n: int = 25) -> str:
    words = text.split()
    return " ".join(words[:n])


# ── Resume ───────────────────────────────────────────────────────────────────


def _split_role(line: str) -> tuple[str, str]:
    line = _RANGE.sub("", line).strip(" |,-–—()")
    for sep in (" at ", " @ ", " | ", " — ", " – ", " - ", ", "):
        if sep in line:
            a, b = [p.strip(" |,-–—") for p in line.split(sep, 1)]
            # Titles usually contain role words; companies usually don't
            if seniority_from_title(b) or re.search(r"engineer|developer|manager|analyst|designer|scientist", b, re.I):
                return b, a
            return a, b
    return line or "Professional", "Unknown company"


def mock_resume(raw_text: str) -> ResumeExtraction:
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    email_m = _EMAIL.search(raw_text)
    email = email_m.group(0) if email_m else None
    phone_m = _PHONE.search(raw_text)
    name, name_idx = None, None
    for i, ln in enumerate(lines[:4]):
        if 1 < len(ln.split()) <= 4 and re.fullmatch(r"[A-Za-z.'\- ]+", ln) and not _HEADER.match(ln):
            name, name_idx = (ln.title() if ln.isupper() else ln), i
            break
    headline = None
    if name_idx is not None and name_idx + 1 < len(lines):
        nxt = lines[name_idx + 1]
        if len(nxt) < 80 and not _EMAIL.search(nxt) and not re.search(r"\d{3}", nxt) and not _HEADER.match(nxt):
            headline = nxt
    loc = re.search(r"\b([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?,\s?(?:[A-Z]{2}|[A-Z][a-z]+))\b", raw_text[:600])

    # Sections
    section = None
    sections: dict[str, list[str]] = {}
    for ln in lines:
        h = _HEADER.match(ln)
        if h:
            key = h.group(1).lower()
            section = ("experience" if "experience" in key or key == "employment" else
                       "skills" if "skills" in key else key)
            continue
        if section:
            sections.setdefault(section, []).append(ln)

    summary = " ".join(sections.get("summary", sections.get("profile", sections.get("about", []))))[:800] or None

    skills = find_skills_in_text(raw_text)
    for ln in sections.get("skills", []):
        for part in re.split(r"[,|;•]|\s{2,}", _BULLET.sub("", ln.split(":", 1)[-1])):
            part = part.strip(" .")
            if 1 < len(part) <= 40 and part not in skills:
                skills.append(part)

    work: list[WorkEntry] = []
    exp_lines = sections.get("experience") or lines
    current: WorkEntry | None = None
    for i, ln in enumerate(exp_lines):
        m = _RANGE.search(ln)
        if m and not _BULLET.match(ln):
            role_line = ln if _RANGE.sub("", ln).strip(" |,-–—") else (exp_lines[i - 1] if i else "")
            title, company = _split_role(role_line)
            current = WorkEntry(company=company, title=title, location=None,
                                start_date=m.group("start"), end_date=m.group("end"), highlights=[])
            work.append(current)
        elif current is not None and (_BULLET.match(ln) or (len(ln) > 40 and not _HEADER.match(ln))):
            current.highlights.append(_BULLET.sub("", ln))

    education: list[EducationEntry] = []
    for ln in sections.get("education", []) or [ln for ln in lines if _DEGREE.search(ln)]:
        inst = _INSTITUTION.search(ln)
        if inst or _DEGREE.search(ln):
            years = re.findall(r"\b(19\d{2}|20\d{2})\b", ln)
            deg = _DEGREE.search(ln)
            education.append(EducationEntry(
                institution=(inst.group(0).strip() if inst else ln[:80]),
                degree=deg.group(0) if deg else None,
                field_of_study=None,
                start_year=int(years[0]) if len(years) > 1 else None,
                end_year=int(years[-1]) if years else None,
            ))
    certs = [_BULLET.sub("", c) for c in sections.get("certifications", sections.get("certification", []))]

    return ResumeExtraction(
        full_name=name, email=email, phone=phone_m.group(0).strip() if phone_m else None,
        location=loc.group(1) if loc else None, headline=headline, summary=summary, skills=skills,
        education=education[:5], work_history=work, certifications=certs, languages=[], links=[],
    )


# ── Job description ──────────────────────────────────────────────────────────


def mock_jd(title: str, description: str) -> JDExtraction:
    required_lines, nice_lines, duty_lines, other = [], [], [], []
    bucket = other
    for raw in description.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        low = ln.lower()
        is_header = len(ln) < 70 and (ln.endswith(":") or not _BULLET.match(ln)) and not low.endswith(".")
        if is_header and re.search(r"nice|preferred|bonus|plus|desirable", low):
            bucket = nice_lines
            continue
        if is_header and re.search(r"requirement|qualification|must|you have|what you bring|skills", low):
            bucket = required_lines
            continue
        if is_header and re.search(r"responsibilit|you will|you.ll|what you.?ll do|duties", low):
            bucket = duty_lines
            continue
        bucket.append(_BULLET.sub("", ln))

    req_text = "\n".join(required_lines) or description
    required = find_skills_in_text(req_text)
    nice = [s for s in find_skills_in_text("\n".join(nice_lines)) if s not in required]
    years = re.search(r"(\d{1,2})\s*\+?\s*(?:-\s*\d+\s*)?(?:years|yrs)", description, re.I)
    edu = next((ln for ln in required_lines + other if _DEGREE.search(ln)), None)
    duties = [d for d in duty_lines if len(d) > 10][:8] or [
        ln for ln in other if len(ln) > 25 and not ln.endswith(":")][:5]
    return JDExtraction(
        role_title=title, seniority=seniority_from_title(title),  # type: ignore[arg-type]
        required_skills=required, nice_to_have_skills=nice,
        min_years_experience=float(years.group(1)) if years else None,
        education_requirement=edu[:160] if edu else None, responsibilities=duties, domain=None,
    )


# ── Screening assessment ─────────────────────────────────────────────────────


def mock_assessment(ctx: dict[str, Any]) -> ScreeningAssessmentLLM:
    gap_status = {m["skill"].lower(): m["status"] for m in ctx["skill_gap"]["matches"]}
    years = ctx["experience"].get("total_years")
    min_years = ctx["jd"].get("min_years_experience")
    verdicts: list[LLMRequirementVerdict] = []
    for req, evidence in zip(ctx["requirements"], ctx["evidence"], strict=True):
        texts = [e["text"] for e in evidence]
        quote = None
        if req["kind"] == "skill":
            status = gap_status.get(req["text"].lower(), "missing")
            verdict = {"matched": "met", "partial": "partial"}.get(status, "not_met")
            hit = next((s for t in texts for s in _sentences(t) if mentioned_in(s, req["text"])), None)
            quote = _clip_words(hit) if hit else None
            reason = (f"Resume shows {req['text']}." if verdict == "met" else
                      f"Related but not direct evidence of {req['text']}." if verdict == "partial" else
                      f"No evidence of {req['text']} in the retrieved excerpts.")
        elif req["kind"] == "education":
            hit = next((s for t in texts for s in _sentences(t) if _DEGREE.search(s)), None)
            verdict = "met" if hit else "not_met"
            quote = _clip_words(hit) if hit else None
            reason = "A relevant degree is listed." if hit else "No degree found in the retrieved excerpts."
        elif req["kind"] == "experience" and min_years:
            ratio = (years or 0) / min_years
            verdict = "met" if ratio >= 1 else "partial" if ratio >= 0.6 else "not_met"
            reason = f"{years or 'Unknown'} years of experience against {min_years:g} required."
        else:
            req_words = {w for w in _words(req["text"]) if len(w) > 3}
            best, best_overlap = None, 0.0
            for t in texts:
                for s in _sentences(t):
                    overlap = len(req_words & set(_words(s))) / max(1, len(req_words))
                    if overlap > best_overlap:
                        best, best_overlap = s, overlap
            verdict = "met" if best_overlap >= 0.5 else "partial" if best_overlap >= 0.2 else "not_met"
            quote = _clip_words(best) if best and verdict != "not_met" else None
            reason = ("Closely matching experience described." if verdict == "met" else
                      "Some related experience described." if verdict == "partial" else
                      "No clearly related experience in the excerpts.")
        verdicts.append(LLMRequirementVerdict(requirement_id=req["id"], verdict=verdict,
                                              evidence_quote=quote, reasoning=reason))

    pts = {"met": 1.0, "partial": 0.5, "not_met": 0.0}
    req_score = sum(pts[v.verdict] for v in verdicts) / max(1, len(verdicts)) * 100
    coverage = ctx["skill_gap"]["required_coverage_pct"]
    fit = int(round(0.7 * req_score + 0.3 * coverage))
    met = [r["text"] for r, v in zip(ctx["requirements"], verdicts, strict=True) if v.verdict == "met"]
    missing = [r["text"] for r, v in zip(ctx["requirements"], verdicts, strict=True) if v.verdict == "not_met"]
    summary = (
        f"The candidate satisfies {len(met)} of {len(verdicts)} assessed requirements"
        + (f", with clear evidence for {', '.join(met[:3])}" if met else "")
        + "." + (f" Gaps remain in {', '.join(missing[:3])}." if missing else " No major gaps were found.")
        + " (Generated by the offline mock model.)"
    )
    kinds = {r["text"]: r["kind"] for r in ctx["requirements"]}
    met_skills = [m for m in met if kinds.get(m) == "skill"] or met
    missing_skills = [m for m in missing if kinds.get(m) == "skill"] or missing
    if not missing:
        one_liner = "Meets every assessed requirement."
    elif met_skills:
        one_liner = f"Strong {', '.join(met_skills[:2])}; no evidence of {missing_skills[0]}."
    else:
        one_liner = f"Little evidence for core requirements such as {missing_skills[0]}."
    return ScreeningAssessmentLLM(
        fit_score=fit, summary=summary, one_liner=one_liner[:140],
        strengths=[f"Demonstrated {m}" for m in met[:4]],
        concerns=[f"No clear evidence of {m}" for m in missing[:4]],
        requirements=verdicts,
    )


# ── Interview ────────────────────────────────────────────────────────────────


def mock_plan(ctx: dict[str, Any]) -> InterviewPlanLLM:
    jd, resume, gap = ctx["jd"], ctx["resume"], ctx.get("skill_gap") or {}
    n = ctx["question_count"]
    role = (resume.get("work_history") or [{}])[0]
    matched = gap.get("matched_required") or jd.get("required_skills", [])
    missing = (gap.get("missing_required") or []) + (gap.get("partial_required") or [])
    qs: list[InterviewQuestion] = []

    def add(category: str, topic: str, question: str, rationale: str, criteria: list[str], req: str | None) -> None:
        qs.append(InterviewQuestion(id=f"q{len(qs) + 1}", category=category, topic=topic,  # type: ignore[arg-type]
                                    question=question, rationale=rationale,
                                    ideal_answer_criteria=criteria, related_requirement=req))

    where = f" as {role.get('title')} at {role.get('company')}" if role.get("title") else ""
    add("experience_deep_dive", "Most relevant experience",
        f"Walk me through the most technically challenging project you owned{where}. What was the problem, "
        "what did you personally do, and what was the result?",
        "Validates depth and ownership in the candidate's most recent role.",
        ["Describes a specific project and their own role", "Explains technical decisions and trade-offs",
         "Quantifies the outcome or impact"], None)
    for skill in matched[:2]:
        add("technical", skill,
            f"Tell me about a time you used {skill} in production. What design decision did you make, and what "
            "trade-offs did you consider?",
            f"{skill} is a core requirement for the role.",
            [f"Shows hands-on {skill} experience", "Explains a concrete design decision", "Discusses trade-offs"],
            skill)
    if missing:
        add("gap_probe", missing[0],
            f"This role relies on {missing[0]}. What related experience do you have, and how would you get "
            "productive with it in your first few months?",
            f"{missing[0]} was not clearly evidenced in the resume.",
            ["Identifies transferable experience", "Proposes a concrete learning plan", "Shows realistic self-assessment"],
            missing[0])
    add("behavioral", "Collaboration",
        "Describe a time you disagreed with a teammate about a technical approach. How did you handle it and what "
        "happened?",
        "Assesses collaboration and communication.",
        ["Describes the disagreement objectively", "Shows listening and evidence-based persuasion",
         "Reflects on the outcome"], None)
    for duty in jd.get("responsibilities", []):
        if len(qs) >= n:
            break
        add("situational", duty[:60],
            f"Imagine your first month in this role involves this: “{duty}”. How would you approach it?",
            "Tests how the candidate would handle a core responsibility.",
            ["Breaks the problem into clear steps", "Identifies risks and stakeholders", "Defines success measures"],
            duty)
    while len(qs) < n:
        add("behavioral", "Learning", "Tell me about something difficult you learned recently. How did you go about "
            "learning it?", "Assesses learning agility.",
            ["Gives a specific example", "Describes a deliberate learning approach"], None)
    return InterviewPlanLLM(
        strategy="Validate depth in the candidate's most relevant experience, confirm core required skills, "
                 "probe the main gap constructively, and assess collaboration. (Offline mock plan.)",
        questions=qs[:n],
    )


def mock_turn(ctx: dict[str, Any]) -> TurnDecision:
    answer = ctx["answer"].strip()
    words = len(answer.split())
    dont_know = re.search(r"\b(don'?t know|not sure|no idea|can'?t (say|share)|pass)\b", answer, re.I)
    if words < 25 and ctx["follow_ups_remaining"] > 0 and not dont_know:
        return TurnDecision(answer_quality="weak", action="follow_up",
                            reply="Thanks. Could you make that more concrete — a specific situation, what you "
                                  "decided, and how it turned out?")
    quality = "strong" if words > 90 else "adequate" if words >= 25 else "non_answer" if dont_know else "weak"
    return TurnDecision(answer_quality=quality, action="next_question",  # type: ignore[arg-type]
                        reply="Thank you, that's helpful context.")


def mock_rubric(ctx: dict[str, Any]) -> InterviewRubricLLM:
    plan, messages = ctx["plan"], ctx["messages"]
    scores: list[QuestionScore] = []
    for q in plan["questions"]:
        answer = " ".join(m["content"] for m in messages if m.get("question_id") == q["id"] and m["role"] == "candidate")
        words = _words(answer)
        n = len(words)
        specifics = len(re.findall(r"\d+%?|because|trade-?off|decid|measur|result|impact|latency|users|scal", answer, re.I))
        criteria = []
        for crit in q["ideal_answer_criteria"]:
            key = {w for w in _words(crit) if len(w) > 4}
            hit = len(key & set(words)) / max(1, len(key))
            met = hit >= 0.34 or (n > 80 and specifics >= 3)
            sent = next((s for s in _sentences(answer) if key & set(_words(s))), None)
            criteria.append(CriterionScore(criterion=crit, met=met, evidence_quote=_clip_words(sent, 20) if sent and met else None,
                                           score=min(10, int(3 + 7 * min(1.0, hit + n / 200)))))
        length = min(1.0, n / 70)
        depth = min(10, int(2 + 6 * length + min(2, specifics / 2)))
        comm = min(10, int(3 + 5 * length + (1 if len(_sentences(answer)) >= 3 else 0)))
        solve = min(10, int(2 + 5 * length + min(3, specifics / 2)))
        met_ratio = sum(c.met for c in criteria) / max(1, len(criteria))
        score = int(round((depth + comm + solve) / 30 * 70 + met_ratio * 30)) if n else 0
        scores.append(QuestionScore(
            question_id=q["id"], technical_depth=depth if n else 0, communication=comm if n else 0,
            problem_solving=solve if n else 0, score=score, criteria=criteria,
            strengths=["Gave specific, concrete detail"] if specifics >= 3 else (["Clear, complete answer"] if n > 60 else []),
            improvements=[] if n > 60 else ["Answer could include more specific examples and outcomes"],
        ))
    overall = int(round(sum(s.score for s in scores) / max(1, len(scores))))
    strong = [q["topic"] for q, s in zip(plan["questions"], scores, strict=True) if s.score >= 70]
    weak = [q["topic"] for q, s in zip(plan["questions"], scores, strict=True) if s.score < 50]
    return InterviewRubricLLM(
        overall_score=overall,
        summary=(f"Overall interview performance scored {overall}/100. "
                 + (f"Strongest on {', '.join(strong[:3])}. " if strong else "")
                 + (f"Answers on {', '.join(weak[:3])} lacked depth. " if weak else "")
                 + "(Generated by the offline mock model.)"),
        question_scores=scores,
        key_strengths=[f"Solid answer on {t}" for t in strong[:3]],
        key_risks=[f"Limited depth on {t}" for t in weak[:3]],
    )


class MockLLM:
    provider = "mock"
    model = "mock-heuristic-v1"

    async def generate(self, *, task: str, system: str, prompt: str, schema: type[T], effort: str = "medium",
                       max_tokens: int = 16000, context: dict[str, Any] | None = None) -> T:
        ctx = context or {}
        if schema is ResumeExtraction:
            return mock_resume(ctx["raw_text"])  # type: ignore[return-value]
        if schema is JDExtraction:
            return mock_jd(ctx["title"], ctx["description"])  # type: ignore[return-value]
        if schema is ScreeningAssessmentLLM:
            return mock_assessment(ctx)  # type: ignore[return-value]
        if schema is InterviewPlanLLM:
            return mock_plan(ctx)  # type: ignore[return-value]
        if schema is TurnDecision:
            return mock_turn(ctx)  # type: ignore[return-value]
        if schema is InterviewRubricLLM:
            return mock_rubric(ctx)  # type: ignore[return-value]
        raise NotImplementedError(f"MockLLM has no handler for {schema.__name__}")
