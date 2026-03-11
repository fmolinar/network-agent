from __future__ import annotations

import re

from network_agent.core.host_os import HostOS
from network_agent.core.schemas import Category, PlannerPlan


class Planner:
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

    def plan(self, user_prompt: str, artifacts: dict[str, str], host_os: HostOS) -> PlannerPlan:
        category = self.classify(user_prompt, artifacts)
        checks_by_category = {
            Category.CONNECTIVITY: ["ping", "traceroute", "logs"],
            Category.DNS: ["logs", "dns_trace", "ping"],
            Category.ROUTING: ["traceroute", "logs", "routing_table", "netstat"],
            Category.TRANSPORT: ["pcap_summary", "tcpdump_summary", "logs", "netstat"],
            Category.SECURITY: ["logs", "pcap_summary", "policy_events"],
            Category.UNKNOWN: ["ping", "traceroute", "logs", "pcap_summary"],
        }

        checks = checks_by_category[category]
        if host_os == HostOS.WINDOWS:
            checks = ["tracert" if c == "traceroute" else c for c in checks]

        return PlannerPlan(
            category=category,
            selected_checks=checks,
            rationale=f"classified as {category.value} on host_os={host_os.value}",
            host_os=host_os,
        )
