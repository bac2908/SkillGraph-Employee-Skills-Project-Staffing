"""New-project recommendation contracts, real API/services, isolated graph doubles."""

from unittest.mock import MagicMock

import pytest

from app.repositories import candidate_repository as candidates
from app.repositories import project_assignment_repository as assignments
from app.repositories import project_repository as projects
from app.repositories import project_requirement_repository as requirements
from app.repositories import skill_repository as skills


@pytest.fixture
def workspace(monkeypatch):
    monkeypatch.setattr(
        projects.graph_db.driver,
        "session",
        MagicMock(side_effect=AssertionError("Live graph forbidden")),
    )
    state = {"project": None, "requirements": [], "team": []}

    def create(data, *, actor):
        state["project"] = dict(data)
        return data

    def require_skill(project_id, skill_id, min_level, priority, *, actor):
        state["requirements"] = [
            {
                "skill_id": skill_id,
                "skill": "Docker",
                "required_level": min_level,
                "priority": priority,
            }
        ]
        return {
            "project_id": project_id,
            "project_name": "New Project",
            "skill_id": skill_id,
            "skill_name": "Docker",
            "category": "DevOps",
            "min_level": min_level,
            "priority": priority,
        }, True

    monkeypatch.setattr(projects, "create_project", create)
    monkeypatch.setattr(
        projects, "project_exists", lambda _: state["project"] is not None
    )
    monkeypatch.setattr(
        projects, "get_required_skills", lambda _: state["requirements"]
    )
    monkeypatch.setattr(projects, "get_team_skill_levels", lambda *_: state["team"])
    monkeypatch.setattr(skills, "get_skill", lambda _: {"skill_id": "SK007"})
    monkeypatch.setattr(requirements, "upsert_project_requirement", require_skill)
    monkeypatch.setattr(candidates, "get_project_member_ids", lambda _: set())
    candidate_read = MagicMock(
        return_value=[
            {
                "employee_id": "EMP001",
                "name": "Synthetic Engineer",
                "email": "engineer@example.com",
                "title": "Developer",
                "seniority": "Senior",
                "location": "Test Office",
                "status": "AVAILABLE",
                "skill_id": "SK007",
                "skill": "Docker",
                "level": 4,
                "years_experience": 2.5,
            }
        ]
    )
    monkeypatch.setattr(candidates, "get_available_candidate_skills", candidate_read)
    monkeypatch.setattr(candidates, "get_previous_collaborations", lambda *_: [])
    monkeypatch.setattr(
        assignments, "get_employee_allocations", lambda _: {"EMP001": []}
    )
    writer = MagicMock(
        side_effect=AssertionError("Recommendation must never assign automatically")
    )
    monkeypatch.setattr(assignments, "upsert_project_assignment", writer)
    return state, candidate_read, writer


def create_project(client):
    return client.post(
        "/api/projects",
        json={
            "project_id": "PROJ950",
            "name": "New Project",
            "description": "We need Docker and Python engineers",
            "status": "PLANNING",
        },
    )


def test_new_project_requires_explicit_skills_then_returns_explainable_candidates(
    authenticated_client, workspace
):
    client = authenticated_client
    _, candidate_read, writer = workspace
    assert create_project(client).status_code == 201
    initial = client.get("/api/projects/PROJ950/recommendations")
    assert initial.status_code == 200
    assert initial.json()["summary"] == {
        "required_skill_count": 0,
        "uncovered_skill_count": 0,
        "candidate_count": 0,
    }
    candidate_read.assert_not_called()  # Description is not parsed into skills.
    assert (
        client.put(
            "/api/projects/PROJ950/requirements/SK007",
            json={"min_level": 3, "priority": "MUST"},
        ).status_code
        == 201
    )
    response = client.get(
        "/api/projects/PROJ950/recommendations?start_date=2026-10-01&end_date=2026-10-31&required_allocation=20&capacity_only=true"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == {
        "required_skill_count": 1,
        "uncovered_skill_count": 1,
        "candidate_count": 1,
    }
    assert data["uncovered_skills"][0]["status"] == "MISSING"
    person = data["candidates"][0]
    assert person["employee_id"] == "EMP001" and person["location"] == "Test Office"
    assert person["matched_skills"][0] == {
        "skill_id": "SK007",
        "skill": "Docker",
        "level": 4,
        "years_experience": 2.5,
        "required_level": 3,
        "priority": "MUST",
        "gap_status": "MISSING",
    }
    assert (
        person["period_remaining_allocation"] == 100 and person["can_allocate"] is True
    )
    writer.assert_not_called()


@pytest.mark.parametrize("covered", [False, True])
def test_no_candidates_is_distinct_from_no_requirements(
    authenticated_client, workspace, covered
):
    state, candidate_read, _ = workspace
    assert create_project(authenticated_client).status_code == 201
    state["requirements"] = [
        {
            "skill_id": "SK007",
            "skill": "Docker",
            "required_level": 3,
            "priority": "MUST",
        }
    ]
    if covered:
        state["team"] = [
            {"skill_id": "SK007", "best_team_level": 4, "employee_count": 1}
        ]
    candidate_read.return_value = []
    response = authenticated_client.get("/api/projects/PROJ950/recommendations")
    assert response.status_code == 200
    assert response.json()["summary"] == {
        "required_skill_count": 1,
        "uncovered_skill_count": 0 if covered else 1,
        "candidate_count": 0,
    }


def test_missing_project_does_not_return_a_setup_state(authenticated_client, workspace):
    assert (
        authenticated_client.get("/api/projects/PROJ950/recommendations").status_code
        == 404
    )


def test_requirement_read_failure_is_not_misreported_as_unconfigured(
    authenticated_client, workspace, monkeypatch
):
    assert create_project(authenticated_client).status_code == 201
    monkeypatch.setattr(
        projects,
        "get_required_skills",
        MagicMock(
            side_effect=projects.ProjectRepositoryError("private database error")
        ),
    )
    response = authenticated_client.get("/api/projects/PROJ950/recommendations")
    assert response.status_code == 503
    assert "private" not in response.text and "summary" not in response.json()
