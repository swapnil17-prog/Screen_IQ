"""AI interview: question plan (LLM contract), per-turn decisions and transcript messages."""

from typing import Literal

from pydantic import BaseModel, Field

QuestionCategory = Literal["technical", "behavioral", "gap_probe", "experience_deep_dive", "situational"]


class InterviewQuestion(BaseModel):
    id: str = Field(description="Sequential id: 'q1', 'q2', ...")
    category: QuestionCategory
    topic: str = Field(description="Skill or trait probed, e.g. 'PostgreSQL indexing'")
    question: str = Field(description="Conversational question text addressed to the candidate")
    rationale: str = Field(description="Why this question matters for this specific candidate")
    ideal_answer_criteria: list[str] = Field(description="2-4 concrete signals of a strong answer")
    related_requirement: str | None = Field(description="The job requirement this question validates")


class InterviewPlanLLM(BaseModel):
    strategy: str = Field(description="2-3 sentences on what this interview focuses on and why")
    questions: list[InterviewQuestion]


class InterviewPlan(InterviewPlanLLM):
    max_follow_ups: int = 1
    estimated_minutes: int = 15
    generated_by: str = ""


class TurnDecision(BaseModel):
    answer_quality: Literal["strong", "adequate", "weak", "off_topic", "non_answer"]
    action: Literal["follow_up", "next_question"]
    reply: str = Field(
        description=(
            "Your message to the candidate. For follow_up: a brief acknowledgement plus ONE probing "
            "follow-up question. For next_question: a brief, neutral one-sentence acknowledgement only "
            "(the next question is appended automatically)."
        )
    )


class ChatMessage(BaseModel):
    role: Literal["assistant", "candidate"]
    content: str
    timestamp: str
    question_id: str | None = None
    kind: Literal["greeting", "question", "follow_up", "acknowledgement", "answer", "closing"] = "question"
