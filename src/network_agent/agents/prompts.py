from __future__ import annotations

import json
from typing import Any

from network_agent.core.schemas import Diagnosis, ExecutionResult, PlannerPlan


def _artifact_preview(artifacts: dict[str, str], max_chars: int = 2400) -> str:
    compact = {k: v.strip()[: max_chars // max(1, len(artifacts))] for k, v in artifacts.items() if v.strip()}
    return json.dumps(compact, indent=2, sort_keys=True)


def _allowed_commands_for_os(host_os: str) -> list[str]:
    by_os = {
        "linux": ["ping", "traceroute", "nslookup", "netstat", "ip -br addr", "arp -a", "tcpdump -nn"],
        "macos": ["ping", "traceroute", "nslookup", "netstat", "ifconfig", "arp -a", "tcpdump -nn"],
        "windows": ["ping", "tracert", "nslookup", "netstat", "ipconfig /all", "route print", "arp -a"],
    }
    return by_os.get(host_os, ["ping", "traceroute", "tracert", "nslookup", "netstat", "arp -a"])


def planner_prompt(user_prompt: str, artifacts: dict[str, str], host_os: str) -> tuple[str, str]:
    system = (
        "You are PlannerAgent for network troubleshooting. "
        "Classify incident category and choose checks that can trigger safe troubleshooting commands. "
        "Return strict JSON keys: category, selected_checks, rationale. "
        "category must be one of: connectivity,dns,routing,transport,security,unknown. "
        "selected_checks values may include: ping,traceroute,tracert,logs,pcap_summary,dns_trace,"
        "routing_table,netstat,tcpdump_summary,policy_events. "
        "Prefer checks missing from artifacts so Executor can run read-only commands to gather evidence."
    )
    user = (
        f"host_os={host_os}\n"
        f"user_prompt={user_prompt}\n"
        f"artifact_keys={sorted(artifacts.keys())}\n"
        f"allowed_command_hints={_allowed_commands_for_os(host_os)}\n"
        f"artifacts={_artifact_preview(artifacts)}"
    )
    return system, user


def generator_prompt(plan: PlannerPlan, user_prompt: str, execution: ExecutionResult) -> tuple[str, str]:
    system = (
        "You are GeneratorAgent for network troubleshooting. "
        "Return strict JSON keys: problem_summary,candidate_causes_ranked,confidence_score,"
        "required_evidence,remediation_plan,proposed_commands. "
        "candidate_causes_ranked must be an array of objects with keys: "
        "title,confidence,required_evidence,remediation_steps. "
        "proposed_commands must be read-only troubleshooting commands compatible with host_os."
    )
    user_payload: dict[str, Any] = {
        "category": plan.category.value,
        "selected_checks": plan.selected_checks,
        "host_os": plan.host_os.value,
        "user_prompt": user_prompt,
        "parsed_outputs": execution.parsed_outputs,
        "missing_checks": execution.missing_checks,
        "network_topology": execution.network_topology,
        "allowed_command_hints": _allowed_commands_for_os(plan.host_os.value),
    }
    return system, json.dumps(user_payload, indent=2, sort_keys=True)


def validator_prompt(diagnosis: Diagnosis, execution: ExecutionResult) -> tuple[str, str]:
    system = (
        "You are ValidatorAgent for network troubleshooting. "
        "Review diagnosis consistency and safety context. "
        "Return strict JSON keys: verdict, confidence, notes, suggested_evidence. "
        "verdict must be one of: accept,caution,reject."
    )
    user_payload: dict[str, Any] = {
        "diagnosis": {
            "problem_summary": diagnosis.problem_summary,
            "confidence_score": diagnosis.confidence_score,
            "required_evidence": diagnosis.required_evidence,
            "proposed_commands": diagnosis.metadata.get("proposed_commands", []),
            "candidate_causes_ranked": [
                {
                    "title": c.title,
                    "confidence": c.confidence,
                    "required_evidence": c.required_evidence,
                }
                for c in diagnosis.candidate_causes_ranked
            ],
        },
        "execution": {
            "executed_checks": execution.executed_checks,
            "missing_checks": execution.missing_checks,
            "host_os": execution.host_os.value,
            "network_topology": execution.network_topology,
        },
    }
    return system, json.dumps(user_payload, indent=2, sort_keys=True)
