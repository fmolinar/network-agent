from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from network_agent.core.host_os import HostOS


class Category(str, Enum):
    CONNECTIVITY = "connectivity"
    DNS = "dns"
    ROUTING = "routing"
    TRANSPORT = "transport"
    SECURITY = "security"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class PlannerPlan:
    category: Category
    selected_checks: list[str]
    rationale: str
    host_os: HostOS


@dataclass(slots=True)
class CandidateCause:
    title: str
    confidence: float
    required_evidence: list[str]
    remediation_steps: list[str]


@dataclass(slots=True)
class Diagnosis:
    problem_summary: str
    candidate_causes_ranked: list[CandidateCause]
    confidence_score: float
    required_evidence: list[str]
    remediation_plan: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ValidationResult:
    valid: bool
    reasons: list[str]
    needs_llm_critic: bool
    blocked_operations: list[str]
    llm_critic: dict[str, Any] = field(default_factory=dict)
    needs_user_confirmation: bool = False
    confirmation_question: str = ""
    chat_should_close: bool = False
    resolved_acknowledgement: str = ""


@dataclass(slots=True)
class ExecutionResult:
    raw_outputs: dict[str, str]
    parsed_outputs: dict[str, dict[str, Any]]
    executed_checks: list[str]
    missing_checks: list[str]
    host_os: HostOS
    network_topology: dict[str, Any] = field(default_factory=dict)
    collection_attempts: dict[str, str] = field(default_factory=dict)
    collection_errors: dict[str, str] = field(default_factory=dict)
