"""Unit tests for the TaskPlanner and DAG dependency validation."""

import pytest
from astra_agent.core.models import PlanStep, TaskInput, TaskPlan
from astra_agent.planning.planner import PlanningError, TaskPlanner
from astra_agent.providers.mock import MockProvider
from astra_agent.tools.registry import ToolRegistry


def test_valid_dag_validation():
    planner = TaskPlanner(provider=MockProvider(), tool_registry=ToolRegistry())

    plan = TaskPlan(
        objective="Valid DAG plan",
        steps=[
            PlanStep(step_id="stp_1", order=1, title="Step 1", description="", tool_name="calculator", dependencies=[]),
            PlanStep(step_id="stp_2", order=2, title="Step 2", description="", tool_name="calculator", dependencies=["stp_1"]),
            PlanStep(step_id="stp_3", order=3, title="Step 3", description="", tool_name="calculator", dependencies=["stp_1", "stp_2"]),
        ]
    )

    # Should not raise
    planner.validate_plan_dag(plan)


def test_cyclic_dag_rejected():
    planner = TaskPlanner(provider=MockProvider(), tool_registry=ToolRegistry())

    plan = TaskPlan(
        objective="Cyclic plan",
        steps=[
            PlanStep(step_id="stp_1", order=1, title="Step 1", description="", tool_name="calculator", dependencies=["stp_2"]),
            PlanStep(step_id="stp_2", order=2, title="Step 2", description="", tool_name="calculator", dependencies=["stp_1"]),
        ]
    )

    with pytest.raises(PlanningError, match="Cyclic dependency"):
        planner.validate_plan_dag(plan)


def test_self_dependency_rejected():
    planner = TaskPlanner(provider=MockProvider(), tool_registry=ToolRegistry())

    plan = TaskPlan(
        objective="Self-dependent plan",
        steps=[
            PlanStep(step_id="stp_1", order=1, title="Step 1", description="", tool_name="calculator", dependencies=["stp_1"]),
        ]
    )

    with pytest.raises(PlanningError, match="cannot depend on itself"):
        planner.validate_plan_dag(plan)


def test_nonexistent_dependency_rejected():
    planner = TaskPlanner(provider=MockProvider(), tool_registry=ToolRegistry())

    plan = TaskPlan(
        objective="Missing dependency plan",
        steps=[
            PlanStep(step_id="stp_1", order=1, title="Step 1", description="", tool_name="calculator", dependencies=["stp_nonexistent"]),
        ]
    )

    with pytest.raises(PlanningError, match="references non-existent dependency"):
        planner.validate_plan_dag(plan)


@pytest.mark.asyncio
async def test_underspecified_objective_rejected():
    planner = TaskPlanner(provider=MockProvider(), tool_registry=ToolRegistry())
    task_in = TaskInput(objective="ab")  # Too short, requires clarification

    with pytest.raises(PlanningError, match="underspecified"):
        await planner.create_plan(task_in)
