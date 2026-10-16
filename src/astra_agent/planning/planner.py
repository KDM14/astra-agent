"""Task planner and DAG dependency resolution."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from astra_agent.core.models import PlanStep, TaskInput, TaskPlan
from astra_agent.core.state import AstraError
from astra_agent.providers.base import BaseLLMProvider, Message
from astra_agent.tools.registry import ToolRegistry


class PlanningError(AstraError):
    """Raised when plan generation or validation fails."""
    pass


class TaskPlanner:
    """Transforms a user objective into an executable, acyclic Plan DAG."""

    def __init__(self, provider: BaseLLMProvider, tool_registry: ToolRegistry):
        self.provider = provider
        self.tool_registry = tool_registry

    def validate_plan_dag(self, plan: TaskPlan) -> None:
        """Validates that step dependencies form a valid Directed Acyclic Graph."""
        step_ids = {s.step_id for s in plan.steps}

        # Check all dependencies refer to real step IDs
        for s in plan.steps:
            for dep in s.dependencies:
                if dep not in step_ids:
                    raise PlanningError(f"Step '{s.step_id}' references non-existent dependency '{dep}'.")
                if dep == s.step_id:
                    raise PlanningError(f"Step '{s.step_id}' cannot depend on itself.")

        # Cycle detection using DFS / in-degree topological sort
        in_degree = {s.step_id: 0 for s in plan.steps}
        adj: Dict[str, List[str]] = {s.step_id: [] for s in plan.steps}

        for s in plan.steps:
            for dep in s.dependencies:
                adj[dep].append(s.step_id)
                in_degree[s.step_id] += 1

        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        visited_count = 0

        while queue:
            node = queue.pop(0)
            visited_count += 1
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count != len(plan.steps):
            raise PlanningError("Cyclic dependency detected in task plan.")

    async def create_plan(self, task_input: TaskInput) -> TaskPlan:
        """Generates a structured plan via LLM or deterministic fallback."""
        objective = task_input.objective.strip()
        if not objective:
            raise PlanningError("Objective cannot be empty.")

        # Clarification check: very short or gibberish input
        if len(objective) < 3:
            raise PlanningError(f"Objective '{objective}' is underspecified. Clarification required.")

        tools_desc = self.tool_registry.describe_all()

        prompt = (
            f"You are the Astra Task Planner. Generate an execution plan for the user objective.\n"
            f"Objective: {objective}\n"
            f"Parameters: {task_input.parameters}\n\n"
            f"Available Tools:\n{json.dumps(tools_desc, indent=2)}\n\n"
            f"Return ONLY valid JSON matching this schema:\n"
            f'{{"objective": "{objective}", "steps": [{{"order": 1, "title": "Step title", "description": "Details", "tool_name": "tool_name", "tool_arguments": {{}}, "dependencies": []}}]}}'
        )

        messages = [
            Message(role="system", content="You are a precise task decomposition system that outputs JSON plans."),
            Message(role="user", content=prompt),
        ]

        resp = await self.provider.generate(messages=messages, temperature=0.0)

        try:
            # Parse response content JSON
            clean_content = resp.content.strip()
            # If wrapped in markdown code fence, strip it
            if clean_content.startswith("```"):
                clean_content = clean_content.split("\n", 1)[1]
                if clean_content.endswith("```"):
                    clean_content = clean_content.rsplit("\n", 1)[0]

            data = json.loads(clean_content)
            steps_data = data.get("steps", [])
            plan_steps = []

            for idx, s in enumerate(steps_data):
                step = PlanStep(
                    step_id=f"stp_{idx+1}",
                    order=s.get("order", idx+1),
                    title=s.get("title", f"Step {idx+1}"),
                    description=s.get("description", ""),
                    tool_name=s.get("tool_name", "state_inspect"),
                    tool_arguments=s.get("tool_arguments", {}),
                    dependencies=s.get("dependencies", []),
                    requires_approval=self.tool_registry.is_sensitive(s.get("tool_name", "")),
                )
                plan_steps.append(step)

            if not plan_steps:
                raise PlanningError("Plan generated with 0 steps.")

            plan = TaskPlan(objective=objective, steps=plan_steps)
            self.validate_plan_dag(plan)
            return plan

        except (json.JSONDecodeError, KeyError) as e:
            raise PlanningError(f"Failed to parse plan from LLM output: {e}\nRaw content: {resp.content}")
