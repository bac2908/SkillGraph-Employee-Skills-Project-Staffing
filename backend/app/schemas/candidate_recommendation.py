from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.schemas.skill_gap import (
    SkillCoverageStatus,
    SkillGapItem,
    SkillPriority,
)


class RecommendationPlan(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    required_allocation: int = Field(default=1, ge=1, le=100)
    capacity_only: bool = False

    @model_validator(mode="after")
    def ordered_dates(self):
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("Provide both start_date and end_date, or neither.")
        if self.start_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
        return self


class CandidateRecommendationSummary(BaseModel):
    uncovered_skill_count: int
    candidate_count: int


class MatchedSkill(BaseModel):
    skill_id: str
    skill: str
    level: int
    years_experience: int | float
    required_level: int
    priority: SkillPriority
    gap_status: SkillCoverageStatus


class Candidate(BaseModel):
    employee_id: str
    name: str
    email: str
    title: str
    seniority: str
    status: str
    location: str
    matched_skills: list[MatchedSkill]
    matched_skill_count: int
    collaboration_count: int
    collaborators: list[str]
    shared_projects: list[str]
    rank: int
    period_peak_allocation: int
    period_remaining_allocation: int
    can_allocate: bool


class CandidateRecommendationResponse(BaseModel):
    project_id: str
    summary: CandidateRecommendationSummary
    uncovered_skills: list[SkillGapItem]
    candidates: list[Candidate]
    start_date: date
    end_date: date
    required_allocation: int
    capacity_only: bool
