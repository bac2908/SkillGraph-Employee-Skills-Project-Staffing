from datetime import date
from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from app.schemas.common import APIModel
from app.schemas.employee import EmployeeId
from app.schemas.project import ProjectId
from app.schemas.skill import SkillId
from app.schemas.skill_gap import SkillPriority

SkillLevel = Annotated[int, Field(ge=1, le=5)]
YearsExperience = Annotated[float, Field(ge=0, le=80)]
AllocationPercent = Annotated[int, Field(ge=1, le=100)]
AssignmentRole = Annotated[
    str,
    StringConstraints(min_length=1, max_length=100),
]


class EmployeeSkillWrite(APIModel):
    expected_version: str | None = Field(default=None, max_length=64)
    level: SkillLevel = Field(examples=[4])
    years_experience: YearsExperience = Field(examples=[2])


class EmployeeSkillRead(EmployeeSkillWrite):
    version: str = "0"
    employee_id: EmployeeId
    employee_name: str
    skill_id: SkillId
    skill_name: str
    category: str


class EmployeeSkillList(APIModel):
    items: list[EmployeeSkillRead]
    total: int


class ProjectAssignmentWrite(APIModel):
    expected_version: str | None = Field(default=None, max_length=64)
    role: AssignmentRole = Field(examples=["Backend Developer"])
    allocation: AllocationPercent = Field(
        description="Percentage of the employee's capacity assigned here.",
        examples=[80],
    )
    start_date: date | None = Field(
        default=None, description="Inclusive; null = no lower bound."
    )
    end_date: date | None = Field(
        default=None, description="Inclusive; null = no upper bound."
    )

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date.")
        return self


class ProjectAssignmentRead(ProjectAssignmentWrite):
    version: str = "0"
    project_id: ProjectId
    project_name: str
    employee_id: EmployeeId
    employee_name: str
    employee_total_allocation: int = Field(
        description="Active allocation today in the UTC+07 business calendar."
    )
    employee_remaining_allocation: int = Field(
        description="100 minus today's active allocation; can be negative for invalid legacy data."
    )
    allocation_as_of: date | None = None
    period_peak_allocation: int | None = None
    period_remaining_allocation: int | None = None


class ProjectAssignmentList(APIModel):
    items: list[ProjectAssignmentRead]
    total: int


class ProjectRequirementWrite(APIModel):
    expected_version: str | None = Field(default=None, max_length=64)
    min_level: SkillLevel = Field(examples=[3])
    priority: SkillPriority = Field(examples=["MUST"])


class ProjectRequirementRead(ProjectRequirementWrite):
    version: str = "0"
    project_id: ProjectId
    project_name: str
    skill_id: SkillId
    skill_name: str
    category: str


class ProjectRequirementList(APIModel):
    items: list[ProjectRequirementRead]
    total: int
