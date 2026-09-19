"""Account audit uses the caller's SQLite transaction, never a second connection."""

import json

from app.core.audit import AuditActor, AuditContext

FIELDS = (
    "user_id",
    "name",
    "email",
    "role",
    "is_active",
    "must_change_password",
    "project_ids",
)


def snapshot(value):
    if value is None:
        return None
    value = dict(value)
    result = {key: value[key] for key in FIELDS if key in value}
    if isinstance(result.get("project_ids"), str):
        result["project_ids"] = json.loads(result["project_ids"])
    for key in ("is_active", "must_change_password"):
        if key in result:
            result[key] = bool(result[key])
    return result


def write_event(db, actor: AuditActor, user_id, action, before, after):
    before, after = snapshot(before), snapshot(after)
    if before == after and action == "UPDATED":
        return
    context = AuditContext.create(actor)
    db.execute(
        "INSERT INTO account_audit VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            context.event_id,
            context.occurred_at,
            actor.user_id,
            actor.name,
            user_id,
            action,
            json.dumps(before, ensure_ascii=False, sort_keys=True),
            json.dumps(after, ensure_ascii=False, sort_keys=True),
        ),
    )


def read_events(db, parameters):
    rows = db.execute(
        "SELECT * FROM account_audit WHERE (:action IS NULL OR action=:action) "
        "AND (:actor IS NULL OR actor_id=:actor OR instr(lower(actor_name),lower(:actor))>0) "
        "AND (:since IS NULL OR occurred_at>=:since) AND (:until IS NULL OR occurred_at<=:until) "
        "AND (:cursor_time IS NULL OR occurred_at<:cursor_time "
        "OR (occurred_at=:cursor_time AND event_id<:cursor_id)) "
        "ORDER BY occurred_at DESC, event_id DESC LIMIT :fetch_limit",
        parameters,
    ).fetchall()
    return [
        {
            "event_id": r["event_id"],
            "occurred_at": r["occurred_at"],
            "actor_id": r["actor_id"],
            "actor_name": r["actor_name"],
            "project_id": None,
            "resource_type": "ACCOUNT",
            "resource_id": r["user_id"],
            "action": r["action"],
            "before": snapshot(json.loads(r["before_json"])),
            "after": snapshot(json.loads(r["after_json"])),
        }
        for r in rows
    ]
