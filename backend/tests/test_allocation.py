"""Temporal allocation contracts. Offline tests never open a real graph."""

from datetime import date
from random import Random
from unittest.mock import MagicMock

import pytest
from neo4j import Record
from pydantic import ValidationError

from app.core.allocation import peak_allocation
from app.core.audit import AuditActor, AuditContext
from app.repositories import activity_repository as activity
from app.repositories import candidate_repository as candidates
from app.repositories import project_assignment_repository as assignments
from app.repositories import project_repository as projects
from app.schemas.relationships import ProjectAssignmentWrite
from app.services.candidate_recommendation_service import CandidateRecommendationService
from scripts.backup_support.graph import graph_summary, validate_properties


@pytest.fixture(autouse=True)
def no_graph(monkeypatch):
    monkeypatch.setattr(
        assignments.graph_db.driver,
        "session",
        MagicMock(side_effect=AssertionError("Live graph forbidden")),
    )


def load(amount, start=None, end=None):
    return {"allocation": amount, "start_date": start, "end_date": end}


@pytest.mark.parametrize(
    "rows,start,end,expected",
    [
        ([], None, None, 0),
        ([{"allocation": 80}], "2026-10-01", "2026-10-31", 80),
        (
            [
                load(60, "2026-10-01", "2026-10-15"),
                load(60, "2026-10-16", "2026-10-31"),
            ],
            "2026-10-01",
            "2026-10-31",
            60,
        ),
        (
            [
                load(60, "2026-10-01", "2026-10-15"),
                load(60, "2026-10-15", "2026-10-31"),
            ],
            None,
            None,
            120,
        ),
        ([load(100, "2026-11-01", "2026-11-30")], "2026-10-01", "2026-10-31", 0),
        ([load(80, None, "2026-09-30"), load(20)], "2026-10-01", None, 20),
        ([load(90, "2026-11-01"), load(10)], "2026-10-01", None, 100),
        ([load(100, "2026-10-01", "2026-10-01")], "2026-10-01", "2026-10-01", 100),
        ([load(100, "9999-12-31", "9999-12-31")], None, None, 100),
        ([load(100, "0001-01-01", "0001-01-01")], None, None, 100),
        ([load(30, "2028-02-29", "2028-02-29")], "2028-02-28", "2028-03-01", 30),
    ],
)
def test_peak_uses_actual_simultaneous_load(rows, start, end, expected):
    assert peak_allocation(rows, start, end) == expected


def test_event_sweep_matches_independent_daily_oracle():
    random = Random(917)
    for _ in range(200):
        rows = []
        for _ in range(random.randrange(15)):
            a, b = sorted([random.randint(1, 28), random.randint(1, 28)])
            rows.append(
                load(random.randint(1, 100), f"2026-02-{a:02}", f"2026-02-{b:02}")
            )
        expected = max(
            sum(
                row["allocation"]
                for row in rows
                if row["start_date"] <= f"2026-02-{d:02}" <= row["end_date"]
            )
            for d in range(1, 29)
        )
        assert peak_allocation(rows, "2026-02-01", "2026-02-28") == expected


@pytest.mark.parametrize(
    "fields",
    [
        {"start_date": "2026-10-02", "end_date": "2026-10-01"},
        {"start_date": "2026-02-29"},
        {"end_date": "wrong"},
        {"allocation": 0},
        {"allocation": 101},
    ],
)
def test_assignment_validation(fields):
    with pytest.raises(ValidationError):
        ProjectAssignmentWrite.model_validate(
            {"role": "Developer", "allocation": 40, **fields}
        )


def result(*rows):
    value = MagicMock()
    value.single.return_value = Record(rows[0]) if rows else None
    value.__iter__.side_effect = lambda: iter(Record(row) for row in rows)
    return value


def test_lock_then_fresh_read_accepts_exactly_100_and_audits_dates(monkeypatch):
    others = [
        load(60, "2026-10-01", "2026-10-15"),
        load(60, "2026-10-16", "2026-10-31"),
    ]
    saved = {
        **load(40, "2026-10-01", "2026-10-31"),
        "project_id": "PROJ001",
        "employee_id": "EMP001",
        "role": "Developer",
    }
    tx = MagicMock()
    tx.run.side_effect = [
        result({"employee_id": "EMP001"}),
        result(*({"assignment": row} for row in others)),
        result({"before": {"allocation": 20, "role": "Developer"}}),
        result(saved),
    ]
    writer = MagicMock()
    monkeypatch.setattr(assignments, "write_event", writer)
    monkeypatch.setattr(assignments, "planning_today", lambda: date(2026, 9, 17))
    context = AuditContext.create(AuditActor("test-admin", "Admin"))
    outcome = assignments._upsert_project_assignment(
        tx, "PROJ001", "EMP001", "Developer", 40, context, "2026-10-01", "2026-10-31"
    )
    assert not outcome.created and not outcome.allocation_exceeded
    assert outcome.allocated_elsewhere == 60
    assert outcome.assignment["employee_total_allocation"] == 0  # future, not today
    assert outcome.assignment["period_peak_allocation"] == 100
    assert outcome.assignment["period_remaining_allocation"] == 0
    assert tx.run.call_args_list[0].args[0] == assignments.LOCK_EMPLOYEE_QUERY
    assert tx.run.call_args_list[1].args[0] == assignments.GET_ALLOCATION_QUERY
    assert (
        tx.run.call_args_list[1].kwargs["project_id"] == "PROJ001"
    )  # old edge excluded
    assert writer.call_args.args[0] is tx
    assert writer.call_args.args[-1]["start_date"] == "2026-10-01"


def test_conflict_on_one_day_has_no_mutation_or_audit(monkeypatch):
    tx = MagicMock()
    tx.run.side_effect = [
        result({"employee_id": "EMP001"}),
        result({"assignment": load(81, "2026-10-15", "2026-10-15")}),
    ]
    writer = MagicMock()
    monkeypatch.setattr(assignments, "write_event", writer)
    response = assignments._upsert_project_assignment(
        tx,
        "PROJ001",
        "EMP001",
        "Dev",
        20,
        AuditContext.create(AuditActor("test", "Test")),
        "2026-10-01",
        "2026-10-31",
    )
    assert response.allocation_exceeded and response.allocated_elsewhere == 81
    assert tx.run.call_count == 2
    writer.assert_not_called()


def test_audit_and_backup_preserve_dates_without_new_graph_types():
    value = {
        "role": "Dev",
        "allocation": 40,
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
    }
    assert activity.snapshot("WORKS_ON", value) == value
    assert activity.snapshot("WORKS_ON", {"allocation": 40}) == activity.snapshot(
        "WORKS_ON", {"allocation": 40, "start_date": None, "end_date": None}
    )
    validate_properties(value)
    archive = {
        "nodes": [
            {
                "ref": "e",
                "labels": ["Employee"],
                "properties": {"employee_id": "EMP001"},
            },
            {
                "ref": "p",
                "labels": ["Project"],
                "properties": {"project_id": "PROJ001"},
            },
        ],
        "relationships": [
            {"start": "e", "end": "p", "type": "WORKS_ON", "properties": value}
        ],
    }
    before = graph_summary(archive)["logical_sha256"]
    value["end_date"] = "2026-10-30"
    assert graph_summary(archive)["logical_sha256"] != before


@pytest.mark.parametrize(
    "query",
    [
        "start_date=2026-10-01",
        "end_date=2026-10-01",
        "start_date=2026-10-02&end_date=2026-10-01",
        "required_allocation=0",
        "required_allocation=101",
        "start_date=nope&end_date=nope",
    ],
)
def test_recommendation_bad_plan_rejected_before_graph(authenticated_client, query):
    response = authenticated_client.get(
        f"/api/projects/PROJ001/recommendations?{query}"
    )
    assert response.status_code == 422


def test_invalid_assignment_dates_rejected_before_graph(authenticated_client):
    response = authenticated_client.put(
        "/api/projects/PROJ001/assignments/EMP001",
        json={
            "role": "Developer",
            "allocation": 40,
            "start_date": "2026-10-02",
            "end_date": "2026-10-01",
        },
    )
    assert response.status_code == 422


@pytest.fixture
def recommendation(monkeypatch):
    service = CandidateRecommendationService()
    skill = {
        "skill_id": "SK001",
        "skill": "Python",
        "required_level": 3,
        "priority": "MUST",
        "status": "MISSING",
        "best_team_level": 0,
        "employee_count": 0,
    }
    monkeypatch.setattr(
        service.skill_gap_service,
        "analyze",
        MagicMock(return_value={"skills": [skill]}),
    )
    monkeypatch.setattr(candidates, "get_project_member_ids", lambda _: {"EMP003"})
    rows = [
        {
            "employee_id": f"EMP00{i}",
            "name": f"Candidate {i}",
            "email": f"c{i}@example.com",
            "title": "Dev",
            "seniority": "Senior",
            "status": "AVAILABLE",
            "location": "Test",
            "skill_id": "SK001",
            "skill": "Python",
            "level": 4,
            "years_experience": 2,
        }
        for i in (1, 2, 3)
    ]
    monkeypatch.setattr(candidates, "get_available_candidate_skills", lambda _: rows)
    monkeypatch.setattr(
        candidates,
        "get_previous_collaborations",
        lambda *_: [
            {
                "employee_id": "EMP001",
                "collaboration_count": 2,
                "collaborators": ["A", "B"],
                "shared_projects": ["Shared"],
            }
        ],
    )
    loads = MagicMock(
        return_value={
            "EMP001": [load(100)],
            "EMP002": [
                load(80, "2026-10-01", "2026-10-15"),
                load(80, "2026-10-16", "2026-10-31"),
            ],
        }
    )
    monkeypatch.setattr(assignments, "get_employee_allocations", loads)
    return service, loads


def test_recommendation_capacity_first_explainable_and_filterable(recommendation):
    service, loads = recommendation
    plan = dict(start_date="2026-10-01", end_date="2026-10-31", required_allocation=20)
    response = service.recommend("PROJ001", **plan)
    assert [c["employee_id"] for c in response["candidates"]] == ["EMP002", "EMP001"]
    assert response["candidates"][0]["period_remaining_allocation"] == 20
    assert response["candidates"][0]["can_allocate"] is True
    assert response["candidates"][1]["can_allocate"] is False
    loads.assert_called_once_with(["EMP001", "EMP002"])
    service.skill_gap_service.analyze.assert_called_once_with(
        "PROJ001", "2026-10-01", "2026-10-31"
    )
    filtered = service.recommend("PROJ001", **plan, capacity_only=True)
    assert filtered["summary"]["candidate_count"] == 1
    assert filtered["candidates"][0]["rank"] == 1


def test_recommendation_capacity_read_failure_never_fabricates_availability(
    recommendation,
):
    service, loads = recommendation
    loads.side_effect = assignments.ProjectAssignmentRepositoryError("offline")
    with pytest.raises(assignments.ProjectAssignmentRepositoryError):
        service.recommend("PROJ001")


def test_list_capacity_today_differs_from_future_period(monkeypatch):
    session = MagicMock()
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session
    monkeypatch.setattr(assignments.graph_db.driver, "session", factory)
    monkeypatch.setattr(assignments, "planning_today", lambda: date(2026, 9, 17))
    session.run.return_value = result(
        {
            "allocation": 40,
            "start_date": "2026-10-01",
            "end_date": "2026-10-31",
            "all_assignments": [
                load(40, "2026-10-01", "2026-10-31"),
                load(50, "2026-09-01", "2026-09-30"),
            ],
        }
    )
    item = assignments.list_project_assignments("PROJ001")[0]
    assert item["employee_total_allocation"] == 50
    assert item["employee_remaining_allocation"] == 50
    assert item["period_peak_allocation"] == 40
    assert item["allocation_as_of"] == "2026-09-17"
    assert "all_assignments" not in item


def test_capacity_batch_read_includes_zero_without_n_plus_one(monkeypatch):
    session = MagicMock()
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session
    monkeypatch.setattr(assignments.graph_db.driver, "session", factory)
    session.run.return_value = result({"employee_id": "EMP001", "assignment": load(40)})
    assert assignments.get_employee_allocations([]) == {}
    factory.assert_not_called()
    rows = assignments.get_employee_allocations(["EMP001", "EMP002"])
    assert rows == {"EMP001": [load(40)], "EMP002": []}
    session.run.assert_called_once_with(
        assignments.CANDIDATE_ALLOCATIONS_QUERY, employee_ids=["EMP001", "EMP002"]
    )


def test_successful_api_write_forwards_dates_and_authenticated_actor(
    authenticated_client, monkeypatch
):
    monkeypatch.setattr(projects, "project_exists", lambda _: True)
    monkeypatch.setattr(
        "app.repositories.employee_repository.get_employee",
        lambda _: {"employee_id": "EMP001"},
    )
    payload = {
        "role": "Developer",
        "allocation": 20,
        "start_date": "2026-10-01",
        "end_date": "2026-10-31",
    }
    data = {
        **payload,
        "project_id": "PROJ001",
        "employee_id": "EMP001",
        "employee_name": "Test",
        "project_name": "Test",
        "employee_total_allocation": 0,
        "employee_remaining_allocation": 100,
        "period_peak_allocation": 20,
        "period_remaining_allocation": 80,
    }
    upsert = MagicMock(return_value=assignments.AssignmentUpsertResult(data, True, 0))
    monkeypatch.setattr(assignments, "upsert_project_assignment", upsert)
    response = authenticated_client.put(
        "/api/projects/PROJ001/assignments/EMP001", json=payload
    )
    assert response.status_code == 201
    assert response.json()["start_date"] == "2026-10-01"
    assert upsert.call_args.kwargs["start_date"] == "2026-10-01"
    assert upsert.call_args.kwargs["end_date"] == "2026-10-31"
    assert (
        upsert.call_args.kwargs["actor"].user_id
        == authenticated_client.get("/api/auth/me").json()["user"]["user_id"]
    )


def test_recommendation_api_serializes_plan_and_capacity(
    authenticated_client, recommendation, monkeypatch
):
    service, _ = recommendation
    monkeypatch.setattr("app.api.projects.candidate_recommendation_service", service)
    response = authenticated_client.get(
        "/api/projects/PROJ001/recommendations?start_date=2026-10-01&end_date=2026-10-31&required_allocation=20&capacity_only=true"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["start_date"] == "2026-10-01" and payload["end_date"] == "2026-10-31"
    assert payload["required_allocation"] == 20 and payload["capacity_only"] is True
    assert payload["candidates"][0]["period_remaining_allocation"] == 20
    assert len(payload["candidates"]) == 1


def test_date_predicates_for_current_coverage_and_previous_collaboration():
    assert "assignment.start_date <= $start_date" in projects.TEAM_SKILL_LEVELS_QUERY
    assert "assignment.end_date >= $end_date" in projects.TEAM_SKILL_LEVELS_QUERY
    assert (
        "member_assignment.start_date <= candidate_assignment.end_date"
        in candidates.COLLABORATION_QUERY
    )
    assert (
        "candidate_assignment.start_date <= member_assignment.end_date"
        in candidates.COLLABORATION_QUERY
    )
