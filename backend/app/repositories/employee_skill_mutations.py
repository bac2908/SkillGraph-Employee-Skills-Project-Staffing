from app.core.audit import AuditActor, AuditContext
from app.core.concurrency import check_version
from app.db.graph import graph_db
from app.repositories.activity_repository import write_event
from app.repositories.errors import RepositoryError

LOCK = """
MATCH (e:Employee {employee_id: $employee_id})
SET e.employee_id = e.employee_id
"""
READ = """
MATCH (e:Employee {employee_id: $employee_id}), (s:Skill {skill_id: $skill_id})
OPTIONAL MATCH (e)-[r:HAS_SKILL]->(s)
RETURN properties(r) AS before, e.name AS employee_name,
       s.name AS skill_name, s.category AS category
"""


def mutate(
    employee_id: str,
    skill_id: str,
    values: dict | None,
    actor: AuditActor,
    expected_version: str | None = None,
):
    audit = AuditContext.create(actor)
    ids = {"employee_id": employee_id, "skill_id": skill_id}

    def write(tx):
        tx.run(LOCK, **ids).consume()
        row = tx.run(READ, **ids).single()
        if row is None:
            raise RepositoryError("Employee or skill does not exist.")
        before = {**row["before"], **ids} if row["before"] is not None else None
        if values is None:
            if before is None:
                return False
            tx.run(
                "MATCH (:Employee {employee_id: $employee_id})-[r:HAS_SKILL]->"
                "(:Skill {skill_id: $skill_id}) DELETE r",
                **ids,
            ).consume()
            after = None
        else:
            check_version(before, expected_version)
            changed = before is None or any(
                before.get(k) != v for k, v in values.items()
            )
            after = {
                **(before or {}),
                **ids,
                **values,
                "version": audit.event_id if changed else before.get("version", "0"),
                "employee_name": row["employee_name"],
                "skill_name": row["skill_name"],
                "category": row["category"],
            }
            if changed:
                saved = tx.run(
                    "MATCH (e:Employee {employee_id: $employee_id}), "
                    "(s:Skill {skill_id: $skill_id}) "
                    "MERGE (e)-[r:HAS_SKILL]->(s) SET r += $values "
                    "RETURN r.version AS version",
                    **ids,
                    values={**values, "version": audit.event_id},
                ).single()
                if saved is None or saved["version"] != audit.event_id:
                    raise RepositoryError("Employee skill was not saved.")
        write_event(
            tx, audit, None, "HAS_SKILL", f"{employee_id}/{skill_id}", before, after
        )
        return True if values is None else (after, before is None)

    try:
        with graph_db.driver.session() as session:
            return session.execute_write(write)
    except RepositoryError:
        raise
    except Exception as exc:
        raise RepositoryError("Unable to change employee skill.") from exc
