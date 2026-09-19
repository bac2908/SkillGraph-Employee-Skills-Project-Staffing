"""Allowlisted node writes: lock, fresh read, validation, data and audit atomically."""

from neo4j.exceptions import ConstraintError

from app.core.audit import AuditActor, AuditContext
from app.core.concurrency import check_version
from app.db.graph import graph_db
from app.repositories.activity_repository import write_event
from app.repositories.errors import DuplicateRecordError, RepositoryError

NODES = {
    "EMPLOYEE": ("Employee", "employee_id"),
    "SKILL": ("Skill", "skill_id"),
    "PROJECT": ("Project", "project_id"),
}


def mutate_node(
    kind: str,
    identity: str,
    operation: str,
    values: dict,
    actor: AuditActor,
    expected_version: str | None = None,
):
    label, key = NODES[kind]  # Identifiers only from this registry, never input.
    audit = AuditContext.create(actor)

    def write(tx):
        before = None
        if operation != "create":
            tx.run(
                f"MATCH (n:{label} {{{key}: $id}}) SET n.{key} = n.{key}", id=identity
            ).consume()
            row = tx.run(
                f"MATCH (n:{label} {{{key}: $id}}) RETURN properties(n) AS data",
                id=identity,
            ).single()
            before = dict(row["data"]) if row else None
            if operation == "update":
                check_version(before, expected_version)
            if before is None:
                return None
        if operation == "delete":
            row = tx.run(
                f"MATCH (n:{label} {{{key}: $id}}) OPTIONAL MATCH (n)-[r]-() "
                "RETURN count(r) AS total",
                id=identity,
            ).single()
            count = row["total"]
            if count:
                return count
            tx.run(f"MATCH (n:{label} {{{key}: $id}}) DELETE n", id=identity).consume()
            after = None
        else:
            changed = before is None or any(
                before.get(k) != v for k, v in values.items()
            )
            if not changed:
                return {**before, "version": before.get("version", "0")}
            properties = {**values, "version": audit.event_id}
            query = (
                f"CREATE (n:{label}) SET n = $properties"
                if operation == "create"
                else f"MATCH (n:{label} {{{key}: $id}}) SET n += $properties"
            )
            row = tx.run(
                query + " RETURN properties(n) AS data",
                id=identity,
                properties=properties,
            ).single()
            if row is None:
                raise RepositoryError("Node mutation was not saved.")
            after = dict(row["data"])
        write_event(
            tx,
            audit,
            identity if kind == "PROJECT" else None,
            kind,
            identity,
            before,
            after,
        )
        return 0 if operation == "delete" else after

    try:
        with graph_db.driver.session() as session:
            return session.execute_write(write)
    except ConstraintError as exc:
        raise DuplicateRecordError("Record already exists.") from exc
    except RepositoryError:
        raise
    except Exception as exc:
        raise RepositoryError("Unable to mutate resource.") from exc
