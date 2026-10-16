"""Specialized role implementations with scoped permissions."""

from __future__ import annotations

from typing import Any, Dict, List
from astra_agent.core.models import PermissionLevel, TaskPlan
from astra_agent.multiagent.contracts import AgentRole, ResearchOutput, ReviewResult
from astra_agent.providers.base import BaseLLMProvider, Message
from astra_agent.tools.registry import ToolRegistry


class ResearcherAgent:
    """Specialized researcher scoped strictly to READ_ONLY tools."""

    role = AgentRole.RESEARCHER
    allowed_permissions = [PermissionLevel.READ_ONLY]

    def __init__(self, provider: BaseLLMProvider, tool_registry: ToolRegistry):
        self.provider = provider
        self.tool_registry = tool_registry

    async def research(self, topic: str, context: Dict[str, Any]) -> ResearchOutput:
        # Search relevant files in workspace
        file_search = self.tool_registry.get("file_search")
        findings = []
        sources = []

        if file_search:
            res = file_search.run({"pattern": "*"})
            if res.success and isinstance(res.output, dict):
                for f in res.output.get("results", [])[:5]:
                    sources.append(f.get("path", ""))

        prompt = f"Synthesize research on topic '{topic}' given sources: {sources}"
        resp = await self.provider.generate([
            Message(role="system", content="You are a factual research agent that cites verified sources."),
            Message(role="user", content=prompt),
        ])

        return ResearchOutput(
            findings=[{"topic": topic, "summary": resp.content}],
            sources=sources,
            summary=resp.content,
        )


class ReviewerAgent:
    """Audits generated code and execution artifacts against security and quality rules."""

    role = AgentRole.REVIEWER
    allowed_permissions = [PermissionLevel.READ_ONLY]

    def __init__(self, provider: BaseLLMProvider):
        self.provider = provider

    async def review_artifacts(self, artifacts: List[Dict[str, Any]], test_results: Dict[str, Any]) -> ReviewResult:
        all_passed = test_results.get("all_passed", True)
        
        # Check for obvious security flaws in artifacts
        comments = []
        security_passed = True
        for art in artifacts:
            content_str = str(art.get("content", ""))
            if "rm -rf" in content_str or "eval(" in content_str:
                security_passed = False
                comments.append(f"Security hazard detected in artifact from {art.get('source')}")

        approved = security_passed and all_passed
        if not all_passed:
            comments.append("Automated test suite reported test failures.")

        return ReviewResult(
            approved=approved,
            security_checks_passed=security_passed,
            evidence_verified=all_passed,
            comments=comments,
            suggested_changes=None if approved else "Fix security hazards and failing unit tests.",
        )
