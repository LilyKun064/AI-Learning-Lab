"""Topic-independent schemas. Rubric IDs and point limits come from configuration."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Table(StrictModel):
    columns: list[str]
    rows: list[list[str | int | float]]


class Activity(StrictModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    question: str = Field(min_length=1)
    scenario: str = ''
    instructions: str = ''
    table: Table | None = None
    data_note: str = ''
    assumptions: list[str] = []
    reflection_prompt: str = 'How did your thinking develop? What remains uncertain?'


class Criterion(StrictModel):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    points: float = Field(gt=0)
    credit_guidance: str


class Rubric(StrictModel):
    activity_id: str
    learning_goals: list[str]
    answer_guidance: str = Field(min_length=1)
    completion_guidance: str
    criteria: list[Criterion] = Field(min_length=1)
    common_misconceptions: list[str] = []
    teaching_notes: list[str] = []


class Evidence(StrictModel):
    turn: int
    quote: str


class AssessmentUpdate(StrictModel):
    criterion_id: str
    points: float
    understanding: Literal['not_yet_demonstrated', 'developing', 'demonstrated', 'contradicted']
    evidence: list[Evidence]
    note: str
    revises_previous: bool


class TutorReply(StrictModel):
    message: str
    move: Literal['clarify', 'probe', 'hint', 'extend', 'acknowledge', 'ready', 'offer_answer', 'direct', 'feedback']
    instructional_purpose: str
    consent: Literal['none', 'explicit_request', 'accepted_offer', 'ambiguous']
    consent_quote: str
    answer_scope: Literal['none', 'partial', 'full']
    assessment_updates: list[AssessmentUpdate]
    final_assessment: list[AssessmentUpdate]


class DeliveryReview(StrictModel):
    approved: bool
    explicit_request: bool
    consent_quote: str
    reveals_unrequested_answer: bool
    repeats_answered_question: bool
    repair_instruction: str
