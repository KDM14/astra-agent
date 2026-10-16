"""Integration tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient

from astra_agent.api.app import create_app
from astra_agent.api.routes import set_orchestrator
from astra_agent.core.config import AstraConfig
from astra_agent.execution.orchestrator import AstraOrchestrator
from astra_agent.providers.deterministic import DeterministicProvider


@pytest.fixture
def test_client(tmp_path):
    cfg = AstraConfig(
        workspace_dir=str(tmp_path),
        database_url=f"sqlite+aiosqlite:///{tmp_path}/api_test.db",
        enable_persistence=True,
    )
    orch = AstraOrchestrator(
        provider=DeterministicProvider(),
        workspace_dir=str(tmp_path),
        config=cfg,
    )
    set_orchestrator(orch)
    app = create_app()
    return TestClient(app)


def test_health_endpoint(test_client):
    res = test_client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["provider"] == "deterministic"


def test_create_and_run_task_endpoint(test_client):
    payload = {
        "objective": "Calculate '25 * 4' and verify math",
        "timeout_seconds": 60.0,
    }
    res = test_client.post("/api/v1/tasks", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["task_id"].startswith("tsk_")
    assert data["success"] is True
    assert data["state"] == "COMPLETED"

    # Verify status endpoint
    status_res = test_client.get(f"/api/v1/tasks/{data['task_id']}/status")
    assert status_res.status_code == 200
    assert status_res.json()["state"] == "COMPLETED"

    # Verify details endpoint
    details_res = test_client.get(f"/api/v1/tasks/{data['task_id']}")
    assert details_res.status_code == 200
    assert details_res.json()["task_id"] == data["task_id"]


def test_cancel_task_endpoint(test_client):
    # Non-existent task returns 400 or 404
    res = test_client.post("/api/v1/tasks/tsk_fake/cancel")
    assert res.status_code == 400
