from app.core.audit import AuditActor
from app.db.graph import graph_db
from app.repositories.employee_skill_mutations import mutate
from app.repositories.errors import RepositoryError

LIST_EMPLOYEE_SKILLS_QUERY = """
MATCH (employee:Employee {employee_id: $employee_id})
      -[employee_skill:HAS_SKILL]->
      (skill:Skill)
RETURN employee.employee_id AS employee_id,
       employee.name AS employee_name,
       skill.skill_id AS skill_id,
       skill.name AS skill_name,
       skill.category AS category,
       employee_skill.level AS level,
       employee_skill.years_experience AS years_experience,
       coalesce(employee_skill.version, '0') AS version
ORDER BY toLower(skill.name), skill.skill_id
"""

EMPLOYEE_SKILL_EXISTS_QUERY = """
MATCH (:Employee {employee_id: $employee_id})
      -[employee_skill:HAS_SKILL]->
      (:Skill {skill_id: $skill_id})
RETURN count(employee_skill) > 0 AS relationship_exists
"""

UPSERT_EMPLOYEE_SKILL_QUERY = """
MATCH (employee:Employee {employee_id: $employee_id})
MATCH (skill:Skill {skill_id: $skill_id})
MERGE (employee)-[employee_skill:HAS_SKILL]->(skill)
SET employee_skill.level = $level,
    employee_skill.years_experience = $years_experience
RETURN employee.employee_id AS employee_id,
       employee.name AS employee_name,
       skill.skill_id AS skill_id,
       skill.name AS skill_name,
       skill.category AS category,
       employee_skill.level AS level,
       employee_skill.years_experience AS years_experience
"""

DELETE_EMPLOYEE_SKILL_QUERY = """
MATCH (employee:Employee {employee_id: $employee_id})
      -[employee_skill:HAS_SKILL]->
      (skill:Skill {skill_id: $skill_id})
DELETE employee_skill
RETURN true AS deleted
"""


class EmployeeSkillRepositoryError(RepositoryError):
    pass


def list_employee_skills(employee_id: str) -> list[dict]:
    try:
        with graph_db.driver.session() as session:
            result = session.run(
                LIST_EMPLOYEE_SKILLS_QUERY,
                employee_id=employee_id,
            )
            return [record.data() for record in result]
    except Exception as exc:
        raise EmployeeSkillRepositoryError("Unable to list employee skills.") from exc


def upsert_employee_skill(
    employee_id: str,
    skill_id: str,
    level: int,
    years_experience: float,
    *,
    actor: AuditActor,
    expected_version: str | None = None,
):
    return mutate(
        employee_id,
        skill_id,
        {"level": level, "years_experience": years_experience},
        actor,
        expected_version,
    )


def delete_employee_skill(
    employee_id: str, skill_id: str, *, actor: AuditActor
) -> bool:
    return mutate(employee_id, skill_id, None, actor)
