from neo4j import Transaction

from app.core.audit import AuditActor
from app.db.graph import graph_db
from app.repositories.errors import RepositoryError
from app.repositories.node_mutations import mutate_node

EMPLOYEE_FIELDS = """
employee.employee_id AS employee_id,
coalesce(employee.version, '0') AS version,
employee.name AS name,
employee.email AS email,
employee.title AS title,
employee.seniority AS seniority,
employee.status AS status,
employee.location AS location
"""

GET_EMPLOYEE_QUERY = f"""
MATCH (employee:Employee {{employee_id: $employee_id}})
RETURN {EMPLOYEE_FIELDS}
"""

LIST_EMPLOYEES_QUERY = f"""
MATCH (employee:Employee)
WHERE ($search IS NULL
       OR toLower(employee.employee_id) CONTAINS toLower($search)
       OR toLower(employee.name) CONTAINS toLower($search)
       OR toLower(employee.email) CONTAINS toLower($search)
       OR toLower(employee.title) CONTAINS toLower($search))
  AND ($status IS NULL OR employee.status = $status)
RETURN {EMPLOYEE_FIELDS}
ORDER BY toLower(employee.name), employee.employee_id
SKIP $offset
LIMIT $limit
"""

COUNT_EMPLOYEES_QUERY = """
MATCH (employee:Employee)
WHERE ($search IS NULL
       OR toLower(employee.employee_id) CONTAINS toLower($search)
       OR toLower(employee.name) CONTAINS toLower($search)
       OR toLower(employee.email) CONTAINS toLower($search)
       OR toLower(employee.title) CONTAINS toLower($search))
  AND ($status IS NULL OR employee.status = $status)
RETURN count(employee) AS total
"""

EMPLOYEE_EMAIL_EXISTS_QUERY = """
MATCH (employee:Employee)
WHERE toLower(employee.email) = toLower($email)
  AND ($exclude_employee_id IS NULL
       OR employee.employee_id <> $exclude_employee_id)
RETURN count(employee) > 0 AS email_exists
"""

CREATE_EMPLOYEE_QUERY = f"""
CREATE (employee:Employee)
SET employee = $properties
RETURN {EMPLOYEE_FIELDS}
"""

UPDATE_EMPLOYEE_QUERY = f"""
MATCH (employee:Employee {{employee_id: $employee_id}})
SET employee += $updates
RETURN {EMPLOYEE_FIELDS}
"""

EMPLOYEE_RELATIONSHIP_COUNT_QUERY = """
MATCH (employee:Employee {employee_id: $employee_id})
OPTIONAL MATCH (employee)-[relationship]-()
RETURN count(relationship) AS relationship_count
"""

DELETE_EMPLOYEE_QUERY = """
MATCH (employee:Employee {employee_id: $employee_id})
DELETE employee
"""


class EmployeeRepositoryError(RepositoryError):
    pass


def _list_employees(
    transaction: Transaction,
    search: str | None,
    employee_status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    parameters = {
        "search": search,
        "status": employee_status,
        "limit": limit,
        "offset": offset,
    }
    total_record = transaction.run(
        COUNT_EMPLOYEES_QUERY,
        **parameters,
    ).single()
    items = [
        record.data() for record in transaction.run(LIST_EMPLOYEES_QUERY, **parameters)
    ]
    return items, total_record["total"] if total_record else 0


def list_employees(
    search: str | None,
    employee_status: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    try:
        with graph_db.driver.session() as session:
            return session.execute_read(
                _list_employees,
                search,
                employee_status,
                limit,
                offset,
            )
    except Exception as exc:
        raise EmployeeRepositoryError("Unable to list employees.") from exc


def get_employee(employee_id: str) -> dict | None:
    try:
        with graph_db.driver.session() as session:
            record = session.run(
                GET_EMPLOYEE_QUERY,
                employee_id=employee_id,
            ).single()
            return record.data() if record else None
    except Exception as exc:
        raise EmployeeRepositoryError("Unable to retrieve employee.") from exc


def employee_email_exists(
    email: str,
    exclude_employee_id: str | None = None,
) -> bool:
    try:
        with graph_db.driver.session() as session:
            record = session.run(
                EMPLOYEE_EMAIL_EXISTS_QUERY,
                email=email,
                exclude_employee_id=exclude_employee_id,
            ).single()
            return bool(record and record["email_exists"])
    except Exception as exc:
        raise EmployeeRepositoryError(
            "Unable to check employee email uniqueness."
        ) from exc


def create_employee(properties: dict, *, actor: AuditActor) -> dict:
    return mutate_node(
        "EMPLOYEE", properties["employee_id"], "create", properties, actor
    )


def update_employee(
    employee_id: str,
    updates: dict,
    *,
    actor: AuditActor,
    expected_version: str | None = None,
) -> dict | None:
    return mutate_node(
        "EMPLOYEE", employee_id, "update", updates, actor, expected_version
    )


def _delete_employee(
    transaction: Transaction,
    employee_id: str,
) -> int | None:
    record = transaction.run(
        EMPLOYEE_RELATIONSHIP_COUNT_QUERY,
        employee_id=employee_id,
    ).single()
    if record is None:
        return None

    relationship_count = record["relationship_count"]
    if relationship_count == 0:
        transaction.run(
            DELETE_EMPLOYEE_QUERY,
            employee_id=employee_id,
        ).consume()
    return relationship_count


def delete_employee(employee_id: str, *, actor: AuditActor) -> int | None:
    return mutate_node("EMPLOYEE", employee_id, "delete", {}, actor)
