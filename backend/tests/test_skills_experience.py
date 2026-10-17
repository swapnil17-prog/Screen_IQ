import pytest

from app.schemas.extraction import WorkEntry
from app.services.embeddings import HashEmbedder
from app.services.experience import analyze_experience, estimate_seniority, parse_year_month, seniority_from_title
from app.services.skill_gap import compute_skill_gap
from app.services.skills import canonicalize, dedupe_skills, find_skills_in_text, mentioned_in


class TestSkills:
    @pytest.mark.parametrize(
        ("raw", "canonical"),
        [("k8s", "Kubernetes"), ("postgres", "PostgreSQL"), ("React.js", "React"), ("nodejs", "Node.js"),
         ("GoLang", "Go"), ("sklearn", "scikit-learn"), ("C#", "C#"), ("Some Niche Tool", "Some Niche Tool")],
    )
    def test_canonicalize(self, raw, canonical):
        assert canonicalize(raw) == canonical

    def test_dedupe_merges_aliases(self):
        assert dedupe_skills(["Postgres", "PostgreSQL", "postgresql", "k8s", "Kubernetes"]) == [
            "PostgreSQL", "Kubernetes",
        ]

    def test_text_scan_skips_ambiguous_terms(self):
        found = find_skills_in_text("Let's go to market with a REST of the team; we used Kubernetes and C++.")
        assert "Kubernetes" in found and "C++" in found
        assert "Go" not in found and "REST APIs" not in found

    def test_mentions_use_word_boundaries(self):
        assert mentioned_in("Built services with Node.js and Express.", "nodejs")
        assert not mentioned_in("javascript developer", "Java")
        assert mentioned_in("Built ASP.NET Core APIs", ".NET")  # via the "asp.net core" alias


class TestExperience:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [("2021-03", (2021, 3)), ("Mar 2021", (2021, 3)), ("03/2021", (2021, 3)), ("2019", (2019, 1)),
         ("September, 2018", (2018, 9)), (None, None), ("sometime", None)],
    )
    def test_parse_year_month(self, value, expected):
        assert parse_year_month(value) == expected

    def test_overlapping_roles_not_double_counted(self):
        roles = [
            WorkEntry(company="A", title="Engineer", location=None, start_date="2018-01", end_date="2020-01", highlights=[]),
            WorkEntry(company="B", title="Consultant", location=None, start_date="2019-01", end_date="2021-01", highlights=[]),
        ]
        analysis = analyze_experience(roles)
        assert analysis.total_years == 3.0  # 2018-01 → 2021-01, not 4 years

    def test_gaps_detected_but_informational(self):
        roles = [
            WorkEntry(company="A", title="Senior Engineer", location=None, start_date="2022-01", end_date="2023-01",
                      highlights=[]),
            WorkEntry(company="B", title="Engineer", location=None, start_date="2019-01", end_date="2020-06",
                      highlights=[]),
        ]
        analysis = analyze_experience(roles)
        assert len(analysis.gaps) == 1 and analysis.gaps[0].months == 19
        assert analysis.progression == "ascending"
        assert analysis.current_title == "Senior Engineer"

    def test_undated_roles_flagged(self):
        analysis = analyze_experience([WorkEntry(company="A", title="Dev", location=None, start_date=None,
                                                 end_date=None, highlights=[])])
        assert analysis.total_years is None
        assert any("without parseable dates" in f for f in analysis.flags)

    def test_seniority(self):
        assert seniority_from_title("Sr. Backend Engineer") == "senior"
        assert seniority_from_title("VP of Engineering") == "executive"
        assert seniority_from_title("Software Engineer") is None
        # inflated title tempered by years
        assert estimate_seniority(1.0, "director") == "junior"
        assert estimate_seniority(12.0, None) == "staff"


class TestSkillGap:
    async def test_exact_alias_mentioned_and_missing(self):
        gap = await compute_skill_gap(
            required_skills=["Python", "Kubernetes", "PostgreSQL", "Terraform"],
            nice_to_have_skills=["Apache Kafka"],
            candidate_skills=["python", "k8s", "Docker"],
            resume_text="Tuned PostgreSQL queries for a Kafka-free architecture.",
            embedder=HashEmbedder(),
        )
        by = {m.skill: m for m in gap.matches}
        assert by["Python"].method == "exact"
        assert by["Kubernetes"].method == "alias"
        assert by["PostgreSQL"].method == "mentioned"
        assert by["Terraform"].status == "missing"
        assert gap.missing_required == ["Terraform"]
        assert gap.required_coverage_pct == 75.0
        assert "Docker" in gap.bonus_skills

    async def test_related_token_gives_partial(self):
        gap = await compute_skill_gap(["AWS Lambda"], [], ["AWS"], "", HashEmbedder())
        assert gap.matches[0].status == "partial"
        assert gap.required_coverage_pct == 50.0
