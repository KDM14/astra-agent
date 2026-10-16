"""Contracts and interfaces for specialized multi-agent roles."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from astra_agent.core.models import PermissionLevel, VerificationResult


class AgentRole(str, Enum):
    """Specialized agent roles with scoped responsibilities."""
    PLANNER = "PLANNER"
    RESEARCHER = "RESEARCHER"
    IMPLEMENTER = "IMPLEMENTER"
    REVIEWER = "REVIEWER"
    VERIFIER = "VERIFIER"


class AgentContract(BaseModel):
    """Defines the boundaries, permissions, and expectations for a role."""
    role: AgentRole
    description: str
    allowed_permissions: List[PermissionLevel]
    required_inputs: List[str]
    output_schema_name: str


class ResearchOutput(BaseModel):
    """Structured artifact returned by Researcher."""
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    summary: str


class ReviewResult(BaseModel):
    """Structured code and artifact audit returned by Reviewer."""
    approved: bool
    security_checks_passed: bool
    evidence_verified: bool
    comments: List[str] = Field(default_factory=list)
    suggested_changes: Optional[str] = None
