"""
LLM output contracts for resume and job-description extraction.

These models are passed to Claude as structured-output schemas, so every field
is *required* (nullable where the information may be absent) — structured
outputs require all properties to be listed as required.
"""

from typing import Literal

from pydantic import BaseModel, Field

Seniority = Literal[
    "intern", "junior", "mid", "senior", "staff", "principal", "lead", "manager", "director", "executive"
]


class EducationEntry(BaseModel):
    institution: str
    degree: str | None = Field(description="e.g. 'B.Sc.', 'Master of Science', or null")
    field_of_study: str | None
    start_year: int | None
    end_year: int | None = Field(description="Graduation year, or null if ongoing / unknown")


class WorkEntry(BaseModel):
    company: str
    title: str
    location: str | None
    start_date: str | None = Field(description="Start as 'YYYY-MM' (or 'YYYY' if month unknown)")
    end_date: str | None = Field(description="End as 'YYYY-MM', 'YYYY', or 'present' for a current role")
    highlights: list[str] = Field(description="Responsibility / achievement bullets, verbatim")


class ResumeExtraction(BaseModel):
    full_name: str | None
    email: str | None
    phone: str | None
    location: str | None
    headline: str | None = Field(description="Current or target professional title")
    summary: str | None
    skills: list[str] = Field(
        description="Individual hard and soft skills, technologies, tools, methods (e.g. 'Python', 'Kubernetes')"
    )
    education: list[EducationEntry]
    work_history: list[WorkEntry] = Field(description="Most recent first")
    certifications: list[str]
    languages: list[str] = Field(description="Spoken languages")
    links: list[str]


class JDExtraction(BaseModel):
    role_title: str
    seniority: Seniority | None
    required_skills: list[str] = Field(description="Explicitly required / must-have skills, one per item")
    nice_to_have_skills: list[str] = Field(description="Preferred / bonus / 'a plus' skills, one per item")
    min_years_experience: float | None = Field(description="Minimum years stated; lower bound of a range")
    education_requirement: str | None
    responsibilities: list[str] = Field(description="Key duties as short phrases (max ~12 words each)")
    domain: str | None = Field(description="Industry or product domain, e.g. 'FinTech'")
