"""
Build retrieval units from a structured resume.

Chunks follow the resume's own structure — one chunk per role (split if long),
plus skills, summary, education and certifications — so every piece of RAG
evidence shown to a recruiter is a coherent, attributable excerpt.
"""

import re
from dataclasses import dataclass

from app.schemas.extraction import ResumeExtraction

MAX_CHUNK_CHARS = 700
OVERLAP_SENTENCES = 1


@dataclass(frozen=True)
class Chunk:
    section: str  # experience | skills | summary | education | certifications | other
    text: str


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def split_text(text: str, max_chars: int = MAX_CHUNK_CHARS, header: str = "") -> list[str]:
    """Greedy sentence packing with one sentence of overlap between chunks."""
    sentences = _sentences(text)
    if not sentences:
        return []
    budget = max(100, max_chars - len(header))
    chunks: list[list[str]] = [[]]
    for sentence in sentences:
        # Hard-wrap pathological run-on "sentences"
        for piece in (sentence[i : i + budget] for i in range(0, len(sentence), budget)):
            current = chunks[-1]
            if current and len(" ".join(current)) + len(piece) + 1 > budget:
                carry = current[-OVERLAP_SENTENCES:] if OVERLAP_SENTENCES else []
                if carry and len(" ".join(carry)) + len(piece) + 1 > budget:
                    carry = []
                chunks.append(list(carry))
                current = chunks[-1]
            current.append(piece)
    return [(header + " ".join(c)).strip() for c in chunks if c]


def build_resume_chunks(resume: ResumeExtraction, raw_text: str) -> list[Chunk]:
    chunks: list[Chunk] = []

    if resume.summary:
        chunks += [Chunk("summary", t) for t in split_text(resume.summary, header="Summary: ")]

    for role in resume.work_history:
        period = " – ".join(p for p in (role.start_date, role.end_date or "present") if p)
        header = f"{role.title} at {role.company}" + (f" ({period})" if period else "") + ": "
        body = " ".join(h.rstrip(".") + "." for h in role.highlights if h.strip())
        pieces = split_text(body, header=header) if body else [header.rstrip(": ")]
        chunks += [Chunk("experience", t) for t in pieces]

    if resume.skills:
        skills_text = "Skills: " + ", ".join(resume.skills)
        for i in range(0, len(skills_text), MAX_CHUNK_CHARS):
            chunks.append(Chunk("skills", skills_text[i : i + MAX_CHUNK_CHARS]))

    for edu in resume.education:
        parts = [p for p in (edu.degree, edu.field_of_study) if p]
        years = "–".join(str(y) for y in (edu.start_year, edu.end_year) if y)
        text = f"Education: {' in '.join(parts) or 'Studies'} at {edu.institution}" + (f" ({years})" if years else "")
        chunks.append(Chunk("education", text))

    if resume.certifications:
        chunks.append(Chunk("certifications", "Certifications: " + "; ".join(resume.certifications)))

    # Fall back to raw text when structured extraction found little experience —
    # evidence must never silently disappear.
    if not resume.work_history:
        chunks += [Chunk("other", t) for t in split_text(raw_text[:12_000])]

    return [c for c in chunks if len(c.text) >= 15]


def build_section_texts(resume: ResumeExtraction) -> dict[str, str]:
    """Whole-section texts for section-level semantic similarity."""
    sections: dict[str, str] = {}
    if resume.skills:
        sections["skills"] = ", ".join(resume.skills)
    if resume.work_history:
        sections["experience"] = "\n".join(
            f"{w.title} at {w.company}. " + " ".join(w.highlights) for w in resume.work_history
        )[:6000]
    if resume.summary or resume.headline:
        sections["summary"] = " ".join(p for p in (resume.headline, resume.summary) if p)
    if resume.education:
        sections["education"] = "; ".join(
            " ".join(p for p in (e.degree, e.field_of_study, e.institution) if p) for e in resume.education
        )
    return sections


def build_profile_text(resume: ResumeExtraction) -> str:
    """Compact whole-candidate text used for talent-pool semantic search."""
    parts = [resume.headline or "", resume.summary or ""]
    parts += [f"{w.title} at {w.company}" for w in resume.work_history[:6]]
    parts.append("Skills: " + ", ".join(resume.skills[:60]))
    return "\n".join(p for p in parts if p)[:4000]
