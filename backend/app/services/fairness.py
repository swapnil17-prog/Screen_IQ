"""
Fairness tooling.

1. `redact_pii` — blind screening. Removes names, contact details, links,
   gendered language, age / family-status / nationality / religion markers and
   institution names before resume or interview text reaches the LLM, so these
   demographic proxies cannot influence a score.

2. `analyze_job_description` — deterministic inclusive-language review of a JD
   (gender-coded words after Gaucher, Friesen & Kay 2011; age, ableist and
   exclusionary phrasing; jargon; requirement bloat), with suggestions.

The counterfactual interview audit (masked vs unmasked scoring) lives in
app.services.evaluation and uses `redact_pii`.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

from app.schemas.fairness import BiasFlag, JDBiasReport

# ── PII / demographic-proxy redaction ────────────────────────────────────────

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_URL = re.compile(r"\b(?:https?://|www\.)\S+|\b(?:linkedin\.com|github\.com|gitlab\.com)/\S+", re.I)
_PHONE_CANDIDATE = re.compile(r"(?<!\w)\+?\(?\d[\d\s().-]{7,}\d(?!\w)")
_PRONOUNS = [
    (re.compile(r"\b(he|she)\b", re.I), "they"),
    (re.compile(r"\b(him|her)\b(?=\s+(?:to|and|in|on|for|with|as|at|by|from)\b|[.,;!?]|$)", re.I), "them"),
    (re.compile(r"\b(his|her|hers)\b", re.I), "their"),
    (re.compile(r"\b(himself|herself)\b", re.I), "themself"),
]
_HONORIFICS = re.compile(r"\b(mr|mrs|ms|miss|mx|sir|madam)\.?\s+(?=[A-Z])", re.I)
_GENDER_TERMS = re.compile(
    r"\b(male|female|man|woman|gentleman|lady|boy|girl|sorority|fraternity|brotherhood|sisterhood)\b", re.I
)
_AGE = re.compile(
    r"\b(?:age[d]?\s*:?\s*\d{2}|\d{2}\s*(?:years?|yrs?)\s*old|d\.?o\.?b\.?\s*:?\s*[\w\s/,.-]{4,20}"
    r"|date of birth\s*:?\s*[\w\s/,.-]{4,20}|born (?:in|on)\s+[\w\s,]{4,20})",
    re.I,
)
_FAMILY = re.compile(
    r"\b(married|unmarried|divorced|widow(?:ed|er)?|husband|wife|spouse|children|kids|pregnan\w*|"
    r"maternity(?: leave)?|paternity(?: leave)?|marital status\s*:?\s*\w+)\b",
    re.I,
)
_NATIONALITY = re.compile(r"\b(?:nationality|citizenship|religion|ethnicity|race|caste)\s*:?\s*[A-Za-z -]{2,30}", re.I)
_RELIGION = re.compile(
    r"\b(church|mosque|synagogue|temple|gurdwara|christian|muslim|islamic|jewish|hindu|sikh|buddhist|catholic)\b",
    re.I,
)


@dataclass
class RedactionResult:
    text: str
    counts: Counter = field(default_factory=Counter)


@dataclass
class RedactionContext:
    """Known identifiers for the candidate (from extraction) to redact precisely."""

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    institutions: list[str] = field(default_factory=list)


def _sub(pattern: re.Pattern[str], repl: str, text: str, counts: Counter, key: str) -> str:
    new, n = pattern.subn(repl, text)
    if n:
        counts[key] += n
    return new


def redact_pii(text: str, ctx: RedactionContext) -> RedactionResult:
    counts: Counter = Counter()
    if not text:
        return RedactionResult(text or "", counts)

    # Literal known values first (most precise)
    if ctx.email:
        text = _sub(re.compile(re.escape(ctx.email), re.I), "[EMAIL]", text, counts, "email")
    text = _sub(_EMAIL, "[EMAIL]", text, counts, "email")
    text = _sub(_URL, "[LINK]", text, counts, "link")

    def _phone(m: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        # 9-15 digits and not a year range like "2019 - 2021"
        if 9 <= len(digits) <= 15 and not re.fullmatch(r"\s*(19|20)\d{2}\s*[-–]\s*(19|20)\d{2}\s*", m.group(0)):
            counts["phone"] += 1
            return "[PHONE]"
        return m.group(0)

    text = _PHONE_CANDIDATE.sub(_phone, text)

    if ctx.full_name and ctx.full_name.strip():
        name = ctx.full_name.strip()
        text = _sub(re.compile(re.escape(name), re.I), "[CANDIDATE]", text, counts, "name")
        for part in {p for p in re.split(r"\s+", name) if len(p) > 2}:
            text = _sub(re.compile(rf"\b{re.escape(part)}\b", re.I), "[CANDIDATE]", text, counts, "name")

    if ctx.location and len(ctx.location.strip()) > 2:
        text = _sub(re.compile(re.escape(ctx.location.strip()), re.I), "[LOCATION]", text, counts, "location")

    for inst in sorted({i.strip() for i in ctx.institutions if i and len(i.strip()) > 3}, key=len, reverse=True):
        text = _sub(re.compile(re.escape(inst), re.I), "[INSTITUTION]", text, counts, "institution")

    text = _sub(_HONORIFICS, "", text, counts, "gender")
    for pattern, repl in _PRONOUNS:
        text = _sub(pattern, repl, text, counts, "gender")
    text = _sub(_GENDER_TERMS, "[PERSON]", text, counts, "gender")
    text = _sub(_AGE, "[AGE]", text, counts, "age")
    text = _sub(_FAMILY, "[REDACTED]", text, counts, "family_status")
    text = _sub(_NATIONALITY, "[REDACTED]", text, counts, "nationality")
    text = _sub(_RELIGION, "[AFFILIATION]", text, counts, "religion")
    return RedactionResult(text, counts)


# ── Job description inclusive-language analysis ──────────────────────────────

# Gaucher, Friesen & Kay (2011) word stems (subset commonly used by gender decoders)
_MASCULINE = [
    "active", "adventurous", "aggress", "ambitio", "assert", "athlet", "autonom", "boast", "challeng",
    "compet", "confident", "courag", "decisive", "determin", "dominan", "domina", "force", "greedy",
    "headstrong", "hierarch", "hostil", "impulsive", "independen", "intellect", "outspoken", "persist",
    "reckless", "stubborn", "superior", "self-confiden", "self-relian", "self-sufficien", "fearless",
    "driven", "ninja", "rockstar", "dominate", "killer",
]
_FEMININE = [
    "affectionate", "cheer", "communal", "compassion", "connect", "considerate", "cooperat", "depend",
    "emotiona", "empath", "gentle", "honest", "interpersonal", "interdependen", "kind", "kinship", "loyal",
    "modest", "nurtur", "pleasant", "polite", "sensitiv", "support", "sympath", "tender", "together",
    "trust", "understand", "warm", "collaborat", "inclusive", "community",
]

# (regex, category, severity, suggestion)
_PHRASES: list[tuple[str, str, str, str]] = [
    # Gendered language
    (r"\b(he|his|him|himself)\b", "exclusionary", "high", "Use 'you' or 'they' to address all candidates."),
    (r"\b(chairman|salesman|salesmen|manpower|foreman|craftsman|workmanlike)\b", "exclusionary", "medium",
     "Use gender-neutral terms (chair, salesperson, workforce, supervisor)."),
    (r"\b(guys)\b", "exclusionary", "low", "Use 'team' or 'everyone'."),
    # Age
    (r"\b(young|youthful)\b", "age", "high", "Describe the work, not the age of the person doing it."),
    (r"\bdigital natives?\b", "age", "high", "Say 'comfortable with modern digital tools'."),
    (r"\brecent (college )?grad(uate)?s?\b", "age", "medium",
     "If the role is entry level, say 'early-career' and welcome career changers."),
    (r"\b(no more than|maximum of|max\.?|up to)\s+\d+\+?\s+years?\b", "age", "high",
     "Capping experience can exclude older candidates; state the skills needed instead."),
    (r"\boverqualified\b", "age", "medium", "Evaluate candidates on fit, not 'over-qualification'."),
    (r"\benergetic\b", "age", "low", "Consider 'motivated' or 'enthusiastic'."),
    # Exclusionary
    (r"\bnative (english )?speakers?\b", "exclusionary", "high", "Say 'fluent in English' (or the level required)."),
    (r"\bculture fit\b", "exclusionary", "medium", "Use 'values alignment' or 'culture add' with concrete values."),
    (r"\b(top[- ]tier|ivy league|elite|prestigious) (universit|college|school)\w*", "exclusionary", "high",
     "Focus on skills and outcomes, not institution prestige."),
    (r"\bno (employment )?gaps\b", "exclusionary", "high",
     "Employment gaps often reflect caregiving or health; don't screen on them."),
    (r"\bclean[- ]shaven\b", "exclusionary", "high", "Remove appearance requirements unrelated to the job."),
    (r"\bwork hard,? play hard\b", "exclusionary", "medium", "Describe actual working norms and flexibility."),
    # Ableist
    (r"\bable[- ]bodied\b", "ableist", "high", "Describe essential physical tasks, and offer accommodations."),
    (r"\bmust be able to (stand|walk|lift|see|hear)\b", "ableist", "medium",
     "Only list physical requirements essential to the role, and mention accommodations."),
    (r"\b(crazy|insane|lame)\b", "ableist", "low", "Use 'intense', 'unusual' or 'extraordinary'."),
    # Jargon that signals an exclusionary culture
    (r"\b(rock ?stars?|ninjas?|gurus?|wizards?|superstars?|unicorns?|jedis?|10x)\b", "jargon", "medium",
     "Use the actual job title; hype terms deter many qualified applicants."),
    (r"\bcrush(ing)? it\b", "jargon", "low", "Describe expected outcomes plainly."),
    (r"\bfast[- ]paced\b", "jargon", "low", "Describe the pace concretely (e.g. release cadence)."),
]

_WORD = re.compile(r"[a-z][a-z-]+")


def _count_coded(words: list[str], stems: list[str]) -> Counter:
    hits: Counter = Counter()
    for w in words:
        if w.startswith("dependenc"):  # "dependencies" is tech vocabulary, not a coded word
            continue
        for stem in stems:
            if w.startswith(stem):
                hits[w] += 1
                break
    return hits


def analyze_job_description(text: str, required_skill_count: int | None = None) -> JDBiasReport:
    lower = text.lower()
    words = _WORD.findall(lower)
    flags: list[BiasFlag] = []

    for pattern, category, severity, suggestion in _PHRASES:
        matches = [m.group(0) for m in re.finditer(pattern, lower)]
        if matches:
            phrase = Counter(matches).most_common(1)[0][0]
            flags.append(
                BiasFlag(
                    category=category,  # type: ignore[arg-type]
                    phrase=phrase,
                    count=len(matches),
                    severity=severity,  # type: ignore[arg-type]
                    suggestion=suggestion,
                )
            )

    masculine = _count_coded(words, _MASCULINE)
    feminine = _count_coded(words, _FEMININE)
    m_total, f_total = sum(masculine.values()), sum(feminine.values())
    if m_total - f_total >= 3 and m_total >= 2 * max(f_total, 1):
        lean = "masculine"
    elif f_total - m_total >= 3 and f_total >= 2 * max(m_total, 1):
        lean = "feminine"
    else:
        lean = "neutral"

    if lean == "masculine":
        top = ", ".join(w for w, _ in masculine.most_common(4))
        flags.append(
            BiasFlag(
                category="masculine_coded",
                phrase=top,
                count=m_total,
                severity="medium" if m_total - f_total < 6 else "high",
                suggestion="Balance with collaborative language; masculine-coded wording lowers appeal to women.",
            )
        )
    elif lean == "feminine":
        top = ", ".join(w for w, _ in feminine.most_common(4))
        flags.append(
            BiasFlag(
                category="feminine_coded",
                phrase=top,
                count=f_total,
                severity="low",
                suggestion="Wording skews feminine-coded; consider balancing for a neutral tone.",
            )
        )

    if required_skill_count and required_skill_count > 10:
        flags.append(
            BiasFlag(
                category="requirements",
                phrase=f"{required_skill_count} required skills",
                count=required_skill_count,
                severity="medium",
                suggestion="Long must-have lists discourage qualified applicants (disproportionately women); "
                "move non-essential items to 'nice to have'.",
            )
        )

    penalty = {"high": 15, "medium": 8, "low": 3}

    def _cost(f: BiasFlag) -> int:
        # Repeated phrases cost more (capped at 2x); aggregate flags count once
        repeats = 1 if f.category in ("masculine_coded", "feminine_coded", "requirements") else min(f.count, 2)
        return penalty[f.severity] * repeats

    score = max(0, min(100, 100 - sum(_cost(f) for f in flags)))
    rating = "inclusive" if score >= 85 else "needs_review" if score >= 65 else "biased"

    if not flags:
        summary = "No biased or exclusionary language detected. Wording reads as inclusive."
    else:
        high = sum(1 for f in flags if f.severity == "high")
        summary = (
            f"{len(flags)} issue{'s' if len(flags) != 1 else ''} found"
            + (f", including {high} high-severity" if high else "")
            + f". Gender-coded wording is {lean}."
        )

    order = {"high": 0, "medium": 1, "low": 2}
    flags.sort(key=lambda f: (order[f.severity], f.category))
    return JDBiasReport(
        score=score,
        rating=rating,  # type: ignore[arg-type]
        gender_lean=lean,  # type: ignore[arg-type]
        masculine_count=m_total,
        feminine_count=f_total,
        word_count=len(words),
        flags=flags,
        summary=summary,
    )
