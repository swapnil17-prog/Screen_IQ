from pydantic import BaseModel, Field, model_validator


class ScoringWeights(BaseModel):
    skills: float = Field(0.30, ge=0, le=1)
    experience: float = Field(0.20, ge=0, le=1)
    semantic: float = Field(0.15, ge=0, le=1)
    assessment: float = Field(0.35, ge=0, le=1)

    @model_validator(mode="after")
    def _non_zero(self) -> "ScoringWeights":
        if self.skills + self.experience + self.semantic + self.assessment <= 0:
            raise ValueError("At least one weight must be greater than zero")
        return self

    def normalised(self) -> dict[str, float]:
        raw = self.model_dump()
        total = sum(raw.values())
        return {k: v / total for k, v in raw.items()}


class FinalWeights(BaseModel):
    screening: float = Field(0.40, ge=0, le=1)
    interview: float = Field(0.60, ge=0, le=1)

    @model_validator(mode="after")
    def _non_zero(self) -> "FinalWeights":
        if self.screening + self.interview <= 0:
            raise ValueError("At least one weight must be greater than zero")
        return self


class OrganizationSettings(BaseModel):
    # Redact names, contact details, pronouns, age & other protected-attribute
    # proxies before resume text reaches the LLM.
    blind_screening: bool = True
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)
    final_weights: FinalWeights = Field(default_factory=FinalWeights)
    interview_question_count: int = Field(5, ge=3, le=8)
    interview_max_follow_ups: int = Field(1, ge=0, le=3)
    # Shortlisting a candidate generates their AI interview and emails them the link.
    auto_invite_on_shortlist: bool = True
    # Public careers page listing open jobs with an apply form.
    careers_page_enabled: bool = True
    # Polite rejection email (only to people who applied or were invited to interview).
    email_rejections: bool = True
    # Reminder before an unfinished interview link expires.
    interview_reminders: bool = True
    # Email the recruiter when a candidate finishes their interview.
    notify_on_interview_complete: bool = True
    # Score delta (0-100 scale) above which the counterfactual audit flags an evaluation
    bias_delta_threshold: float = Field(5.0, ge=1, le=30)
