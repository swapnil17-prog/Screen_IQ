"""
Deterministic experience analysis over extracted work history.

Computes total experience as the *union* of dated role intervals (overlapping
roles aren't double-counted), tenure statistics, employment gaps, seniority
and career progression. Everything here is reproducible and explainable —
no LLM involved.
"""

import itertools
import re
from datetime import UTC, datetime

from app.schemas.extraction import WorkEntry
from app.schemas.screening import EmploymentGap, ExperienceAnalysis, ExperienceRole

_MONTHS = {
    m: i + 1
    for i, names in enumerate(
        [
            ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"),
            ("may",), ("jun", "june"), ("jul", "july"), ("aug", "august"),
            ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"), ("dec", "december"),
        ]
    )
    for m in names
}
_PRESENT = {"present", "current", "now", "today", "ongoing", "till date", "to date"}

# Ordered from most to least senior so the first hit wins
_SENIORITY_PATTERNS: list[tuple[str, str]] = [
    ("executive", r"\b(chief|cto|ceo|cfo|coo|cio|vp|vice president|head of|founder|co-founder)\b"),
    ("director", r"\bdirector\b"),
    ("principal", r"\b(principal|distinguished|fellow|architect)\b"),
    ("staff", r"\bstaff\b"),
    ("manager", r"\b(manager|management)\b"),
    ("lead", r"\b(lead|team lead|tech lead)\b"),
    ("senior", r"\b(senior|sr\.?)\b"),
    ("intern", r"\b(intern|internship|trainee|apprentice)\b"),
    ("junior", r"\b(junior|jr\.?|associate|graduate|entry[- ]level)\b"),
]

SENIORITY_RANK = {
    "intern": 0, "junior": 1, "mid": 2, "senior": 3, "lead": 4, "staff": 4,
    "manager": 4, "principal": 5, "director": 6, "executive": 7,
}


def _now_ym() -> tuple[int, int]:
    now = datetime.now(UTC)
    return now.year, now.month


def parse_year_month(value: str | None, *, is_end: bool = False) -> tuple[int, int] | None:
    """Parse 'YYYY-MM', 'YYYY', 'Mar 2021', '03/2021', 'present' → (year, month)."""
    if not value:
        return None
    v = value.strip().lower()
    if v in _PRESENT or any(p in v for p in _PRESENT):
        return _now_ym() if is_end else None
    if m := re.match(r"^(\d{4})[-/.](\d{1,2})", v):
        year, month = int(m.group(1)), int(m.group(2))
    elif m := re.match(r"^(\d{1,2})[-/.](\d{4})$", v):
        month, year = int(m.group(1)), int(m.group(2))
    elif m := re.search(r"([a-z]{3,9})\.?\s*,?\s*(\d{4})", v):
        month = _MONTHS.get(m.group(1))
        year = int(m.group(2))
        if month is None:
            month = 1
    elif m := re.search(r"\b(19\d{2}|20\d{2})\b", v):
        year, month = int(m.group(1)), 1
    else:
        return None
    if not (1950 <= year <= 2100) or not (1 <= month <= 12):
        return None
    return year, month


def _months_between(a: tuple[int, int], b: tuple[int, int]) -> int:
    return (b[0] - a[0]) * 12 + (b[1] - a[1])


def _fmt(ym: tuple[int, int]) -> str:
    return f"{ym[0]:04d}-{ym[1]:02d}"


def seniority_from_title(title: str) -> str | None:
    t = title.lower()
    for level, pattern in _SENIORITY_PATTERNS:
        if re.search(pattern, t):
            return level
    return None


def estimate_seniority(total_years: float | None, latest_title_level: str | None) -> str | None:
    by_years = None
    if total_years is not None:
        if total_years < 3:
            by_years = "junior"
        elif total_years < 6:
            by_years = "mid"
        elif total_years < 10:
            by_years = "senior"
        else:
            by_years = "staff"
    if latest_title_level and by_years:
        # Titles are strong signals but years temper inflated titles
        if SENIORITY_RANK[latest_title_level] - SENIORITY_RANK[by_years] >= 3:
            return by_years
        return latest_title_level
    return latest_title_level or by_years


def analyze_experience(work_history: list[WorkEntry]) -> ExperienceAnalysis:
    roles: list[ExperienceRole] = []
    intervals: list[tuple[tuple[int, int], tuple[int, int]]] = []

    for entry in work_history:
        start = parse_year_month(entry.start_date)
        end_raw = (entry.end_date or "").strip().lower()
        is_current = not end_raw or end_raw in _PRESENT or any(p in end_raw for p in _PRESENT)
        end = _now_ym() if is_current else parse_year_month(entry.end_date, is_end=True)
        months = None
        if start and end and _months_between(start, end) >= 0:
            months = max(1, _months_between(start, end))
            intervals.append((start, end))
        roles.append(
            ExperienceRole(
                company=entry.company,
                title=entry.title,
                start=_fmt(start) if start else None,
                end=None if is_current else (_fmt(end) if end else None),
                months=months,
                is_current=bool(is_current and start),
                seniority=seniority_from_title(entry.title),
            )
        )

    analysis = ExperienceAnalysis(roles=roles, role_count=len(roles))
    if not roles:
        analysis.flags.append("No work history found in the resume")
        return analysis

    # Union of intervals → total experience without double counting overlaps
    merged: list[list[tuple[int, int]]] = []
    for start, end in sorted(intervals):
        if merged and _months_between(merged[-1][1], start) <= 1:
            if end > merged[-1][1]:
                merged[-1][1] = end
        else:
            merged.append([start, end])
    if merged:
        total_months = sum(max(1, _months_between(s, e)) for s, e in merged)
        analysis.total_years = round(total_months / 12, 1)

    for (_, prev_end), (next_start, _) in itertools.pairwise(merged):
        gap = _months_between(prev_end, next_start)
        if gap >= 6:
            analysis.gaps.append(EmploymentGap(start=_fmt(prev_end), end=_fmt(next_start), months=gap))

    dated = [r.months for r in roles if r.months]
    if dated:
        analysis.average_tenure_months = round(sum(dated) / len(dated), 1)
        analysis.longest_tenure_months = max(dated)

    # Most recent role: current roles first, then latest start
    def recency(r: ExperienceRole) -> tuple[int, str]:
        return (1 if r.is_current else 0, r.end or r.start or "")

    latest = max(roles, key=recency)
    analysis.current_title = latest.title
    analysis.current_company = latest.company
    analysis.seniority_estimate = estimate_seniority(analysis.total_years, latest.seniority)

    chronological = sorted((r for r in roles if r.start), key=lambda r: r.start or "")
    ranks = [SENIORITY_RANK.get(r.seniority or "mid", 2) for r in chronological]
    if len(ranks) >= 2:
        if all(b >= a for a, b in itertools.pairwise(ranks)):
            analysis.progression = "ascending" if ranks[-1] > ranks[0] else "stable"
        else:
            analysis.progression = "mixed"

    if len(dated) >= 3 and analysis.average_tenure_months and analysis.average_tenure_months < 14:
        analysis.flags.append(
            f"Short average tenure ({analysis.average_tenure_months:.0f} months across {len(dated)} roles)"
        )
    undated = sum(1 for r in roles if r.months is None)
    if undated:
        analysis.flags.append(f"{undated} role(s) without parseable dates — experience total may be understated")
    return analysis
