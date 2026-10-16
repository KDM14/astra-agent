"""Deterministic rule-based provider for offline benchmark evaluations."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional
from astra_agent.providers.base import BaseLLMProvider, LLMResponse, Message, TokenUsage


class DeterministicProvider(BaseLLMProvider):
    """Generates realistic, deterministic plans and tool calls based on user objectives."""

    name = "deterministic"

    async def generate(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        user_text = ""
        for m in reversed(messages):
            if m.role == "user":
                user_text = m.content
                break

        user_lower = user_text.lower()

        # Check if model is being asked to produce a structured plan
        if "plan" in user_lower and ("objective" in user_lower or "planner" in user_lower or "execution" in user_lower):
            plan = self._generate_plan(user_text)
            return LLMResponse(
                content=json.dumps(plan),
                tool_calls=[],
                usage=TokenUsage(prompt_tokens=150, completion_tokens=120, total_tokens=270, estimated_cost_usd=0.0),
            )

        # Check if this is a step action call
        tool_call = self._determine_tool_call(user_text, messages)
        if tool_call:
            return LLMResponse(
                content="Executing required action.",
                tool_calls=[tool_call],
                usage=TokenUsage(prompt_tokens=100, completion_tokens=60, total_tokens=160, estimated_cost_usd=0.0),
            )

        # Default completion
        return LLMResponse(
            content="Task objective has been accomplished based on verified execution evidence.",
            tool_calls=[],
            usage=TokenUsage(prompt_tokens=80, completion_tokens=40, total_tokens=120, estimated_cost_usd=0.0),
        )

    def _generate_plan(self, prompt: str) -> Dict[str, Any]:
        """Synthesizes a realistic plan matching the objective."""
        p_lower = prompt.lower()

        # Extract objective from prompt if present
        obj_match = re.search(r"Objective:\s*(.*?)(?:\n|$)", prompt)
        objective = obj_match.group(1).strip() if obj_match else prompt[:100]
        obj_lower = objective.lower()

        steps = []
        if "calculate" in obj_lower or "math" in obj_lower:
            # Extract expression inside quotes or digits
            expr_match = re.search(r"['\"]([^'\"]+)['\"]", objective)
            if expr_match:
                expr = expr_match.group(1)
            else:
                num_match = re.search(r"(\d+\s*[\+\-\*\/]\s*\d+)", objective)
                expr = num_match.group(1) if num_match else "42 * 2"

            steps.append({
                "order": 1,
                "title": "Compute calculation",
                "description": f"Calculate expression {expr}",
                "tool_name": "calculator",
                "tool_arguments": {"expression": expr},
                "dependencies": [],
            })

        elif "write" in obj_lower or "destination file" in obj_lower:
            steps.append({
                "order": 1,
                "title": "Write destination file",
                "description": "Write expected content to target file",
                "tool_name": "file_writer",
                "tool_arguments": {"path": "output.txt", "content": "Sample verified output data\n"},
                "dependencies": [],
            })
            steps.append({
                "order": 2,
                "title": "Read back destination file",
                "description": "Verify file readability and content",
                "tool_name": "file_reader",
                "tool_arguments": {"path": "output.txt"},
                "dependencies": ["stp_1"],
            })

        elif "test" in obj_lower or "pytest" in obj_lower:
            steps.append({
                "order": 1,
                "title": "Run test suite",
                "description": "Execute pytest tests in workspace",
                "tool_name": "test_runner",
                "tool_arguments": {"test_path": "tests"},
                "dependencies": [],
            })

        elif "python" in obj_lower or "script" in obj_lower:
            steps.append({
                "order": 1,
                "title": "Execute Python script",
                "description": "Run script in isolated sandbox",
                "tool_name": "python_exec",
                "tool_arguments": {"code": "print('Sandbox Python execution successful')"},
                "dependencies": [],
            })

        else:
            steps.append({
                "order": 1,
                "title": "Search workspace",
                "description": "Locate relevant workspace files",
                "tool_name": "file_search",
                "tool_arguments": {"pattern": "*"},
                "dependencies": [],
            })

        return {
            "objective": objective,
            "steps": steps,
        }

    def _determine_tool_call(self, prompt: str, messages: List[Message]) -> Optional[Dict[str, Any]]:
        p_lower = prompt.lower()
        if "calculate" in p_lower:
            return {
                "id": "call_det_calc",
                "type": "function",
                "function": {
                    "name": "calculator",
                    "arguments": {"expression": "25 * 4"},
                }
            }
        return None
