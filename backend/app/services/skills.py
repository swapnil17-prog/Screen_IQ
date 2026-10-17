"""Skill normalisation, categorisation and in-text mention detection."""

import re
from functools import lru_cache

from app.services.skill_taxonomy import TAXONOMY

# Terms that are too ambiguous to detect in free text ("Go", "R", "rest", "shell",
# "security"...). They still match against an explicit skills list.
_TEXT_SCAN_EXCLUDE = {
    "go", "r", "c", "rest", "cv", "tf", "dl", "ml", "sh", "shell", "security", "architecture",
    "spring", "node", "express", "oracle", "lambda", "analytics", "ux", "swift", "rust", "ruby",
    "dart", "julia", "elixir", "excel", "monitoring", "leadership", "communication", "collaboration",
    "ownership", "accountability", "coaching", "teamwork", "agile", "kanban", "scrum", "linux", "unix",
    "git", "rails", "s3", "ec2", "containers", "serverless", "vue", "mongo", "torch", "spark", "kafka",
    "airflow", "tableau", "keras", "elk", "chroma", "helm", "problem solving", "mentoring",
    "statistics", "accounting", "seo", "experimentation", "dsa", "oop", "pmp", "sfdc", "hcl", "psql",
}


def normalize_key(skill: str) -> str:
    """Case/punctuation-insensitive key that keeps meaningful symbols (c++, c#, .net)."""
    s = skill.lower().strip()
    s = re.sub(r"[\"'`()\[\]{}]", "", s)
    s = re.sub(r"[/_,;:|]+", " ", s)
    s = re.sub(r"\s*-\s*", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .")


def _compact(key: str) -> str:
    return re.sub(r"[\s.\-]", "", key)


@lru_cache(maxsize=1)
def _alias_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for canonical, (_, aliases) in TAXONOMY.items():
        for term in [canonical, *aliases]:
            key = normalize_key(term)
            index.setdefault(key, canonical)
            index.setdefault(_compact(key), canonical)
    return index


def canonicalize(skill: str) -> str:
    """Map a skill to its canonical taxonomy name, or return it cleaned up."""
    cleaned = re.sub(r"\s+", " ", skill).strip().strip(".,;")
    key = normalize_key(cleaned)
    index = _alias_index()
    return index.get(key) or index.get(_compact(key)) or cleaned


def is_known(skill: str) -> bool:
    return canonicalize(skill) in TAXONOMY


def category_of(skill: str) -> str:
    entry = TAXONOMY.get(canonicalize(skill))
    return entry[0] if entry else "other"


def dedupe_skills(skills: list[str]) -> list[str]:
    """Canonicalise and de-duplicate, preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in skills:
        if not raw or not raw.strip() or len(raw) > 80:
            continue
        name = canonicalize(raw)
        key = normalize_key(name)
        if key and key not in seen:
            seen.add(key)
            out.append(name)
    return out


def _term_pattern(term: str) -> re.Pattern[str]:
    # Custom boundaries so "c++", "c#", ".net" and "node.js" match as whole terms
    return re.compile(r"(?<![\w+#.])" + re.escape(term) + r"(?![\w+#]|\.\w)", re.IGNORECASE)


@lru_cache(maxsize=4096)
def _patterns_for(skill: str) -> tuple[re.Pattern[str], ...]:
    canonical = canonicalize(skill)
    terms = {skill.strip(), canonical}
    if canonical in TAXONOMY:
        terms.update(TAXONOMY[canonical][1])
    usable = [t for t in terms if t and len(t) >= 2 and normalize_key(t) not in _TEXT_SCAN_EXCLUDE]
    return tuple(_term_pattern(t) for t in usable)


def mentioned_in(text: str, skill: str) -> bool:
    """True if the skill (or a known, unambiguous alias) appears as a whole term in text."""
    if not text:
        return False
    return any(p.search(text) for p in _patterns_for(skill))


@lru_cache(maxsize=1)
def _scan_patterns() -> list[tuple[str, re.Pattern[str]]]:
    patterns: list[tuple[str, re.Pattern[str]]] = []
    for canonical, (_, aliases) in TAXONOMY.items():
        for term in [canonical, *aliases]:
            if normalize_key(term) in _TEXT_SCAN_EXCLUDE or len(term) < 3:
                continue
            patterns.append((canonical, _term_pattern(term)))
    return patterns


def find_skills_in_text(text: str) -> list[str]:
    """Detect unambiguous taxonomy skills mentioned anywhere in free text."""
    found: list[str] = []
    seen: set[str] = set()
    for canonical, pattern in _scan_patterns():
        if canonical not in seen and pattern.search(text):
            seen.add(canonical)
            found.append(canonical)
    return found


def tokens(skill: str) -> set[str]:
    return {t for t in re.split(r"[\s/\-]+", normalize_key(skill)) if len(t) >= 2}
