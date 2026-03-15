from __future__ import annotations

import re

from network_agent.agents.prompts import planner_prompt
from network_agent.core.agent_llm import AgentLLMConnector
from network_agent.core.host_os import HostOS
from network_agent.core.schemas import Category, PlannerPlan


class Planner:
    def __init__(self, llm_connector: AgentLLMConnector | None = None) -> None:
        self.llm_connector = llm_connector

    def classify(self, user_prompt: str, artifacts: dict[str, str]) -> Category:
        text = f"{user_prompt}\n" + "\n".join(artifacts.values())
        low = text.lower()

        dns_failures_positive = bool(re.search(r"dns_failures\s*=\s*[1-9]\d*", low))
        dns_error_terms = ["nxdomain", "name resolution", "servfail", "resolver", "getaddrinfo failed"]
        if dns_failures_positive or any(k in low for k in dns_error_terms):
            return Category.DNS
        reach_intent = bool(re.search(r"\b(can|cannot|can't)\s+reach\b", low))
        if reach_intent or any(k in low for k in ["cannot reach", "can't reach", "no internet", "unreachable", "host down"]):
            return Category.CONNECTIVITY
        if any(k in low for k in ["tls", "certificate", "blocked", "firewall", "policy"]):
            return Category.SECURITY
        if any(k in low for k in ["traceroute", "tracert", "hop", "route", "gateway"]):
            return Category.ROUTING
        if any(k in low for k in ["reset", "retransmit", "tcp", "port", "connection refused"]):
            return Category.TRANSPORT
        return Category.UNKNOWN

    def _checks_by_category(self) -> dict[Category, list[str]]:
        return {
            Category.CONNECTIVITY: ["ping", "traceroute", "logs"],
            Category.DNS: ["logs", "dns_trace", "ping"],
            Category.ROUTING: ["traceroute", "logs", "routing_table", "netstat"],
            Category.TRANSPORT: ["pcap_summary", "tcpdump_summary", "logs", "netstat"],
            Category.SECURITY: ["logs", "pcap_summary", "policy_events"],
            Category.UNKNOWN: ["ping", "traceroute", "logs", "pcap_summary"],
        }

    def _normalize_checks(self, checks: list[str], host_os: HostOS, fallback: list[str]) -> list[str]:
        allowed = {
            "ping",
            "traceroute",
            "tracert",
            "logs",
            "pcap_summary",
            "dns_trace",
            "routing_table",
            "netstat",
            "tcpdump_summary",
            "policy_events",
        }
        normalized = [c for c in checks if c in allowed]
        if host_os == HostOS.WINDOWS:
            normalized = ["tracert" if c == "traceroute" else c for c in normalized]
        if not normalized:
            normalized = fallback
        return normalized

    def _llm_plan(self, user_prompt: str, artifacts: dict[str, str], host_os: HostOS) -> PlannerPlan | None:
        if self.llm_connector is None:
            return None
        system, user = planner_prompt(user_prompt, artifacts, host_os.value)
        llm_plan = self.llm_connector.ask_json(system, user, task="planner")
        category_raw = str(llm_plan.get("category", "")).strip().lower()
        try:
            category = Category(category_raw)
        except ValueError:
            return None
        default_checks = self._checks_by_category()[category]
        if host_os == HostOS.WINDOWS:
            default_checks = ["tracert" if c == "traceroute" else c for c in default_checks]
        selected_checks = llm_plan.get("selected_checks", [])
        selected_checks = selected_checks if isinstance(selected_checks, list) else []
        checks = self._normalize_checks([str(c) for c in selected_checks], host_os, default_checks)
        rationale = str(llm_plan.get("rationale") or f"llm-assisted classification as {category.value}")
        return PlannerPlan(category=category, selected_checks=checks, rationale=rationale, host_os=host_os)

    def plan(self, user_prompt: str, artifacts: dict[str, str], host_os: HostOS) -> PlannerPlan:
        llm_plan = self._llm_plan(user_prompt, artifacts, host_os)
        if llm_plan is not None:
            return llm_plan

        category = self.classify(user_prompt, artifacts)
        checks = self._checks_by_category()[category]
        checks = self._normalize_checks(checks, host_os, checks)
        return PlannerPlan(category=category, selected_checks=checks, rationale=f"classified as {category.value} on host_os={host_os.value}", host_os=host_os)
