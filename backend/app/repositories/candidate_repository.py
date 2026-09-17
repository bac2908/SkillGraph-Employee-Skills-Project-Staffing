from app.core.allocation import planning_today
from app.db.graph import graph_db
from app.repositories.errors import RepositoryError

PROJECT_MEMBER_IDS_QUERY = """
MATCH (employee:Employee)-[:WORKS_ON]->
      (project:Project {project_id: $project_id})
RETURN employee.employee_id AS employee_id
ORDER BY employee.employee_id
"""

AVAILABLE_CANDIDATE_SKILLS_QUERY = """
MATCH (candidate:Employee)-[employee_skill:HAS_SKILL]->(skill:Skill)
WHERE candidate.status = $employee_status
  AND skill.skill_id IN $skill_ids
RETURN candidate.employee_id AS employee_id,
       candidate.name AS name,
       candidate.email AS email,
       candidate.title AS title,
       candidate.seniority AS seniority,
       candidate.status AS status,
       candidate.location AS location,
       skill.skill_id AS skill_id,
       skill.name AS skill,
       employee_skill.level AS level,
       employee_skill.years_experience AS years_experience
ORDER BY candidate.employee_id, skill.name
"""

COLLABORATION_QUERY = """
MATCH (candidate:Employee)-[candidate_assignment:WORKS_ON]->
      (shared_project:Project)<-[member_assignment:WORKS_ON]-
      (member:Employee)-[target_assignment:WORKS_ON]->
      (target_project:Project {project_id: $project_id})
WHERE candidate.employee_id IN $candidate_ids
  AND candidate.employee_id <> member.employee_id
  AND shared_project.project_id <> $project_id
  AND (target_assignment.start_date IS NULL OR target_assignment.start_date <= $start_date)
  AND (target_assignment.end_date IS NULL OR target_assignment.end_date >= $end_date)
  AND (candidate_assignment.start_date IS NULL OR candidate_assignment.start_date <= $today)
  AND (member_assignment.start_date IS NULL OR member_assignment.start_date <= $today)
  AND (candidate_assignment.end_date IS NULL OR member_assignment.start_date IS NULL
       OR member_assignment.start_date <= candidate_assignment.end_date)
  AND (member_assignment.end_date IS NULL OR candidate_assignment.start_date IS NULL
       OR candidate_assignment.start_date <= member_assignment.end_date)
RETURN candidate.employee_id AS employee_id,
       count(DISTINCT member) AS collaboration_count,
       collect(DISTINCT member.name) AS collaborators,
       collect(DISTINCT shared_project.name) AS shared_projects
ORDER BY candidate.employee_id
"""


class CandidateRepositoryError(RepositoryError):
    pass


def get_project_member_ids(project_id: str) -> set[str]:
    try:
        with graph_db.driver.session() as session:
            result = session.run(
                PROJECT_MEMBER_IDS_QUERY,
                project_id=project_id,
            )
            return {record["employee_id"] for record in result}
    except Exception as exc:
        raise CandidateRepositoryError(
            "Unable to retrieve the project's current members."
        ) from exc


def get_available_candidate_skills(skill_ids: list[str]) -> list[dict]:
    if not skill_ids:
        return []

    try:
        with graph_db.driver.session() as session:
            result = session.run(
                AVAILABLE_CANDIDATE_SKILLS_QUERY,
                employee_status="AVAILABLE",
                skill_ids=skill_ids,
            )
            return [record.data() for record in result]
    except Exception as exc:
        raise CandidateRepositoryError(
            "Unable to retrieve available candidates."
        ) from exc


def get_previous_collaborations(
    project_id: str,
    candidate_ids: list[str],
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    if not candidate_ids:
        return []

    try:
        with graph_db.driver.session() as session:
            result = session.run(
                COLLABORATION_QUERY,
                project_id=project_id,
                candidate_ids=candidate_ids,
                today=planning_today().isoformat(),
                start_date=start_date or planning_today().isoformat(),
                end_date=end_date or start_date or planning_today().isoformat(),
            )
            return [record.data() for record in result]
    except Exception as exc:
        raise CandidateRepositoryError(
            "Unable to retrieve previous collaborations."
        ) from exc
