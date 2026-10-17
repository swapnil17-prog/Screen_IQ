from app.services.fairness import RedactionContext, analyze_job_description, redact_pii

CTX = RedactionContext(
    full_name="Maria Gonzalez",
    email="maria.g@example.com",
    phone="+1 (415) 555-0100",
    location="Austin, TX",
    institutions=["Stanford University"],
)


class TestRedaction:
    def test_identity_and_contact_removed(self):
        text = ("Maria Gonzalez — maria.g@example.com, +1 (415) 555-0100, Austin, TX. "
                "linkedin.com/in/mariag. Maria led a team of 5. Stanford University, 2015.")
        red = redact_pii(text, CTX)
        for leaked in ("Maria", "Gonzalez", "example.com", "555-0100", "Austin", "linkedin", "Stanford"):
            assert leaked not in red.text
        assert red.counts["name"] >= 2 and red.counts["email"] == 1 and red.counts["institution"] == 1

    def test_demographic_proxies(self):
        text = "She is 34 years old, married with two children. Mrs. Smith volunteers at her church. Nationality: Spanish"
        red = redact_pii(text, RedactionContext())
        low = red.text.lower()
        assert "she " not in low and "34 years old" not in low and "married" not in low
        assert "children" not in low and "church" not in low and "spanish" not in low
        assert {"gender", "age", "family_status", "religion", "nationality"} <= set(red.counts)

    def test_does_not_mangle_technical_text(self):
        text = "Built a single-page app with single sign-on; worked 2019 - 2021 on 10 services."
        red = redact_pii(text, RedactionContext())
        assert red.text == text
        assert not red.counts


class TestJDAnalysis:
    def test_clean_description_is_inclusive(self):
        report = analyze_job_description(
            "You will collaborate with a supportive team to build reliable services. "
            "We value clear communication and welcome candidates from all backgrounds."
        )
        assert report.rating == "inclusive"
        assert report.score >= 85
        assert not [f for f in report.flags if f.severity == "high"]

    def test_biased_description_flagged_with_suggestions(self):
        report = analyze_job_description(
            "We want a young rockstar ninja. He must be a native English speaker and a strong culture fit "
            "who can dominate a competitive, aggressive market."
        )
        categories = {f.category for f in report.flags}
        assert {"age", "exclusionary", "jargon", "masculine_coded"} <= categories
        assert report.rating == "biased"
        assert report.gender_lean == "masculine"
        assert all(f.suggestion for f in report.flags)

    def test_requirement_bloat(self):
        report = analyze_job_description("Build things.", required_skill_count=14)
        assert any(f.category == "requirements" for f in report.flags)
