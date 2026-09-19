from dataclasses import dataclass

from neo4j import Transaction

from app.core.allocation import peak_allocation, planning_today
from app.core.audit import AuditActor, AuditContext
from app.core.concurrency import check_version
from app.db.graph import graph_db
from app.repositories.activity_repository import write_event
from app.repositories.errors import RepositoryError

LIST_PROJECT_ASSIGNMENTS_QUERY = """
MATCH (employee:Employee)
      -[assignment:WORKS_ON]->
      (project:Project {project_id: $project_id})
OPTIONAL MATCH (employee)-[all_assignment:WORKS_ON]->(:Project)
WITH employee, project, assignment,
     collect(properties(all_assignment)) AS all_assignments
RETURN project.project_id AS project_id,
       project.name AS project_name,
       employee.employee_id AS employee_id,
       employee.name AS employee_name,
       assignment.role AS role,
       coalesce(assignment.version, '0') AS version,
       assignment.allocation AS allocation,
       assignment.start_date AS start_date,
       assignment.end_date AS end_date,
       all_assignments
ORDER BY toLower(employee.name), employee.employee_id
"""

LOCK_EMPLOYEE_QUERY = """
MATCH (employee:Employee {employee_id: $employee_id})
SET employee.employee_id = employee.employee_id
RETURN employee.employee_id AS employee_id
"""

GET_ALLOCATION_QUERY = """
MATCH (:Employee {employee_id: $employee_id})-[assignment:WORKS_ON]->(project:Project)
WHERE project.project_id <> $project_id
RETURN properties(assignment) AS assignment
"""

CANDIDATE_ALLOCATIONS_QUERY = """
MATCH (employee:Employee)-[assignment:WORKS_ON]->(:Project)
WHERE employee.employee_id IN $employee_ids
RETURN employee.employee_id AS employee_id, properties(assignment) AS assignment
"""

PROJECT_ASSIGNMENT_EXISTS_QUERY = """
MATCH (:Employee {employee_id: $employee_id})
      -[assignment:WORKS_ON]->
      (:Project {project_id: $project_id})
RETURN properties(assignment) AS before
"""

UPSERT_PROJECT_ASSIGNMENT_QUERY = """
MATCH (employee:Employee {employee_id: $employee_id})
MATCH (project:Project {project_id: $project_id})
MERGE (employee)-[assignment:WORKS_ON]->(project)
SET assignment.role = $role,
    assignment.allocation = $allocation,
    assignment.start_date = $start_date,
    assignment.end_date = $end_date,
    assignment.version = $version
RETURN project.project_id AS project_id,
       project.name AS project_name,
       employee.employee_id AS employee_id,
       employee.name AS employee_name,
       assignment.role AS role,
       coalesce(assignment.version, '0') AS version,
       assignment.allocation AS allocation,
       assignment.start_date AS start_date,
       assignment.end_date AS end_date
"""

DELETE_PROJECT_ASSIGNMENT_QUERY = """
MATCH (employee:Employee {employee_id: $employee_id})
      -[assignment:WORKS_ON]->
      (project:Project {project_id: $project_id})
DELETE assignment
RETURN true AS deleted
"""


@dataclass(frozen=True, slots=True)
class AssignmentUpsertResult:
    assignment: dict | None
    created: bool
    allocated_elsewhere: int

    @property
    def allocation_exceeded(self) -> bool:
        return self.assignment is None


class ProjectAssignmentRepositoryError(RepositoryError):
    pass


def list_project_assignments(project_id: str) -> list[dict]:
    try:
        with graph_db.driver.session() as session:
            result = session.run(
                LIST_PROJECT_ASSIGNMENTS_QUERY,
                project_id=project_id,
            )
            items = [record.data() for record in result]
            today = planning_today()
            for item in items:
                _attach_capacity(item, item.pop("all_assignments"), today)
            return items
    except Exception as exc:
        raise ProjectAssignmentRepositoryError(
            "Unable to list project assignments."
        ) from exc


def _attach_capacity(assignment: dict, all_assignments: list[dict], today) -> None:
    total = peak_allocation(all_assignments, today, today)
    peak = peak_allocation(
        all_assignments, assignment.get("start_date"), assignment.get("end_date")
    )
    assignment.update(
        employee_total_allocation=total,
        employee_remaining_allocation=100 - total,
        allocation_as_of=today.isoformat(),
        period_peak_allocation=peak,
        period_remaining_allocation=100 - peak,
    )


def get_employee_allocations(employee_ids: list[str]) -> dict[str, list[dict]]:
    """One batched read; never a graph call per candidate."""
    grouped = {identity: [] for identity in employee_ids}
    if not employee_ids:
        return grouped
    try:
        with graph_db.driver.session() as session:
            for record in session.run(
                CANDIDATE_ALLOCATIONS_QUERY, employee_ids=employee_ids
            ):
                grouped[record["employee_id"]].append(record["assignment"])
        return grouped
    except Exception as exc:
        raise ProjectAssignmentRepositoryError(
            "Unable to retrieve candidate capacity."
        ) from exc


def _upsert_project_assignment(
    transaction: Transaction,
    project_id: str,
    employee_id: str,
    role: str,
    allocation: int,
    audit: AuditContext,
    start_date: str | None = None,
    end_date: str | None = None,
    expected_version: str | None = None,
) -> AssignmentUpsertResult:
    # Acquire the shared employee write lock BEFORE reading any other assignment.
    # Keep lock, read, validation, MERGE and audit in the same write transaction.
    employee = transaction.run(
        LOCK_EMPLOYEE_QUERY,
        employee_id=employee_id,
    ).single()
    if employee is None:
        raise ProjectAssignmentRepositoryError("Employee does not exist.")

    others = [
        record["assignment"]
        for record in transaction.run(
            GET_ALLOCATION_QUERY, project_id=project_id, employee_id=employee_id
        )
    ]
    allocated_elsewhere = peak_allocation(others, start_date, end_date)
    if allocated_elsewhere + allocation > 100:
        return AssignmentUpsertResult(
            assignment=None,
            created=False,
            allocated_elsewhere=allocated_elsewhere,
        )

    exists_record = transaction.run(
        PROJECT_ASSIGNMENT_EXISTS_QUERY,
        project_id=project_id,
        employee_id=employee_id,
    ).single()
    before = (
        {
            **exists_record["before"],
            "project_id": project_id,
            "employee_id": employee_id,
        }
        if exists_record
        else None
    )

    check_version(before, expected_version)
    changed = before is None or any(
        before.get(k) != v
        for k, v in {
            "role": role,
            "allocation": allocation,
            "start_date": start_date,
            "end_date": end_date,
        }.items()
    )
    record = transaction.run(
        UPSERT_PROJECT_ASSIGNMENT_QUERY,
        version=audit.event_id if changed else before.get("version", "0"),
        project_id=project_id,
        employee_id=employee_id,
        role=role,
        allocation=allocation,
        start_date=start_date,
        end_date=end_date,
    ).single()
    if record is None:
        raise ProjectAssignmentRepositoryError("Project assignment was not saved.")

    assignment = record.data()
    write_event(
        transaction,
        audit,
        project_id,
        "WORKS_ON",
        f"{project_id}/{employee_id}",
        before,
        assignment,
    )
    _attach_capacity(assignment, [*others, assignment], planning_today())
    return AssignmentUpsertResult(
        assignment=assignment,
        created=before is None,
        allocated_elsewhere=allocated_elsewhere,
    )


def upsert_project_assignment(
    project_id: str,
    employee_id: str,
    role: str,
    allocation: int,
    *,
    actor: AuditActor,
    start_date: str | None = None,
    end_date: str | None = None,
    expected_version: str | None = None,
) -> AssignmentUpsertResult:
    audit = AuditContext.create(actor)
    try:
        with graph_db.driver.session() as session:
            return session.execute_write(
                _upsert_project_assignment,
                project_id,
                employee_id,
                role,
                allocation,
                audit,
                start_date,
                end_date,
                expected_version,
            )
    except RepositoryError:
        raise
    except Exception as exc:
        raise ProjectAssignmentRepositoryError(
            "Unable to save project assignment."
        ) from exc


def _delete_project_assignment(
    transaction: Transaction, project_id: str, employee_id: str, audit: AuditContext
) -> bool:
    # Same employee lock as upsert: capture the exact state that is being deleted.
    transaction.run(LOCK_EMPLOYEE_QUERY, employee_id=employee_id).consume()
    existing = transaction.run(
        PROJECT_ASSIGNMENT_EXISTS_QUERY, project_id=project_id, employee_id=employee_id
    ).single()
    if existing is None:
        return False
    record = transaction.run(
        DELETE_PROJECT_ASSIGNMENT_QUERY, project_id=project_id, employee_id=employee_id
    ).single()
    if not record or not record["deleted"]:
        raise ProjectAssignmentRepositoryError("Project assignment was not deleted.")
    before = {
        **existing["before"],
        "project_id": project_id,
        "employee_id": employee_id,
    }
    write_event(
        transaction,
        audit,
        project_id,
        "WORKS_ON",
        f"{project_id}/{employee_id}",
        before,
        None,
    )
    return True


def delete_project_assignment(
    project_id: str, employee_id: str, *, actor: AuditActor
) -> bool:
    audit = AuditContext.create(actor)
    try:
        with graph_db.driver.session() as session:
            return session.execute_write(
                _delete_project_assignment, project_id, employee_id, audit
            )
    except Exception as exc:
        raise ProjectAssignmentRepositoryError(
            "Unable to delete project assignment."
        ) from exc
