from __future__ import annotations

from dataclasses import dataclass
import re

from network_agent.core.host_os import HostOS
from network_agent.core.schemas import ExecutionResult, PlannerPlan
from network_agent.parsers.log_parser import parse_logs
from network_agent.parsers.pcap_parser import parse_pcap_summary
from network_agent.parsers.ping_parser import parse_ping_output
from network_agent.parsers.topology_parser import parse_topology_snapshot
from network_agent.parsers.traceroute_parser import parse_traceroute_output
from network_agent.tools.network_checks import WhitelistedShellRunner


@dataclass(slots=True)
class Executor:
    runner: WhitelistedShellRunner | None = None

    def _extract_target(self, user_prompt: str) -> str:
        ip_match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", user_prompt)
        if ip_match:
            return ip_match.group(0)
        host_match = re.search(r"\b[a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", user_prompt)
        if host_match:
            return host_match.group(0)
        return "8.8.8.8"

    def _check_command(self, check: str, host_os: HostOS, target: str) -> str | None:
        if check == "ping":
            # Windows default per-echo timeout is long; bound each reply wait to 1s.
            return f"ping -n 4 -w 1000 {target}" if host_os == HostOS.WINDOWS else f"ping -c 4 {target}"
        if check in {"traceroute", "tracert"}:
            return f"tracert {target}" if host_os == HostOS.WINDOWS else f"traceroute {target}"
        if check == "dns_trace":
            return f"nslookup {target}"
        if check == "routing_table":
            if host_os == HostOS.WINDOWS:
                return "route print"
            return "netstat -rn"
        if check == "netstat":
            return "netstat -an"
        if check == "arp_table":
            return "arp -a"
        if check == "interface_info":
            if host_os == HostOS.WINDOWS:
                return "ipconfig /all"
            if host_os == HostOS.MACOS:
                return "ifconfig"
            return "ip -br addr"
        if check in {"pcap_summary", "tcpdump_summary"} and host_os != HostOS.WINDOWS:
            # Read-only sampling. This may fail on hosts without privileges.
            return "tcpdump -nn -c 50"
        return None

    def _first_available(self, artifacts: dict[str, str], keys: list[str]) -> str | None:
        for key in keys:
            if key in artifacts:
                return artifacts[key]
        return None

    def _collect_if_possible(
        self,
        check: str,
        plan: PlannerPlan,
        user_prompt: str,
        collect_live_stats: bool,
        allow_config_changes: bool,
        attempts: dict[str, str],
        errors: dict[str, str],
    ) -> str | None:
        if not collect_live_stats or self.runner is None:
            return None
        command = self._check_command(check, plan.host_os, self._extract_target(user_prompt))
        if not command:
            return None
        attempts[check] = command
        try:
            return self.runner.run(command, user_approved=allow_config_changes)
        except Exception as exc:
            errors[check] = str(exc)
            return None

    def run(
        self,
        plan: PlannerPlan,
        artifacts: dict[str, str],
        user_prompt: str = "",
        collect_live_stats: bool = False,
        allow_config_changes: bool = False,
        include_topology: bool = True,
    ) -> ExecutionResult:
        parsed: dict[str, dict] = {}
        raw_outputs: dict[str, str] = {}
        missing_checks: list[str] = []
        collection_attempts: dict[str, str] = {}
        collection_errors: dict[str, str] = {}

        trace_keys = ["tracert", "traceroute"] if plan.host_os == HostOS.WINDOWS else ["traceroute", "tracert"]
        dns_keys = ["dns_trace", "dig", "nslookup", "dns"]
        route_keys = ["routing_table", "route_print", "route"]

        for check in plan.selected_checks:
            if check == "ping":
                raw = self._first_available(artifacts, ["ping"])
                if not raw:
                    raw = self._collect_if_possible(
                        "ping",
                        plan,
                        user_prompt,
                        collect_live_stats,
                        allow_config_changes,
                        collection_attempts,
                        collection_errors,
                    )
                if raw:
                    raw_outputs["ping"] = raw
                    parsed["ping"] = parse_ping_output(raw)
                else:
                    missing_checks.append("ping")
            elif check in {"traceroute", "tracert"}:
                raw = self._first_available(artifacts, trace_keys)
                if not raw:
                    raw = self._collect_if_possible(
                        check,
                        plan,
                        user_prompt,
                        collect_live_stats,
                        allow_config_changes,
                        collection_attempts,
                        collection_errors,
                    )
                if raw:
                    raw_outputs["traceroute"] = raw
                    parsed["traceroute"] = parse_traceroute_output(raw)
                else:
                    missing_checks.append("traceroute")
            elif check in {"logs", "policy_events"}:
                raw = self._first_available(artifacts, ["logs", "event_logs"])
                if raw:
                    raw_outputs["logs"] = raw
                    parsed["logs"] = parse_logs(raw)
                else:
                    missing_checks.append(check)
            elif check == "pcap_summary":
                raw = self._first_available(artifacts, ["pcap_summary", "pcap"])
                if not raw:
                    raw = self._collect_if_possible(
                        "pcap_summary",
                        plan,
                        user_prompt,
                        collect_live_stats,
                        allow_config_changes,
                        collection_attempts,
                        collection_errors,
                    )
                if raw:
                    raw_outputs["pcap_summary"] = raw
                    parsed["pcap_summary"] = parse_pcap_summary(raw)
                else:
                    missing_checks.append("pcap_summary")
            elif check == "dns_trace":
                raw = self._first_available(artifacts, dns_keys)
                if not raw:
                    raw = self._collect_if_possible(
                        "dns_trace",
                        plan,
                        user_prompt,
                        collect_live_stats,
                        allow_config_changes,
                        collection_attempts,
                        collection_errors,
                    )
                if raw:
                    raw_outputs["dns_trace"] = raw
                    parsed["dns_trace"] = {"present": True}
                else:
                    missing_checks.append("dns_trace")
            elif check == "routing_table":
                raw = self._first_available(artifacts, route_keys)
                if not raw:
                    raw = self._collect_if_possible(
                        "routing_table",
                        plan,
                        user_prompt,
                        collect_live_stats,
                        allow_config_changes,
                        collection_attempts,
                        collection_errors,
                    )
                if raw:
                    raw_outputs["routing_table"] = raw
                    parsed["routing_table"] = {"present": True}
                else:
                    missing_checks.append("routing_table")
            elif check == "netstat":
                raw = self._first_available(artifacts, ["netstat"])
                if not raw:
                    raw = self._collect_if_possible(
                        "netstat",
                        plan,
                        user_prompt,
                        collect_live_stats,
                        allow_config_changes,
                        collection_attempts,
                        collection_errors,
                    )
                if raw:
                    raw_outputs["netstat"] = raw
                    parsed["netstat"] = {"present": True}
                else:
                    missing_checks.append("netstat")
            elif check == "tcpdump_summary":
                raw = self._first_available(artifacts, ["tcpdump_summary", "pcap_summary", "pcap"])
                if not raw:
                    raw = self._collect_if_possible(
                        "tcpdump_summary",
                        plan,
                        user_prompt,
                        collect_live_stats,
                        allow_config_changes,
                        collection_attempts,
                        collection_errors,
                    )
                if raw:
                    raw_outputs["tcpdump_summary"] = raw
                    parsed["tcpdump_summary"] = {"present": True}
                else:
                    missing_checks.append("tcpdump_summary")

        topology_sources: dict[str, str] = {}
        for key in ["traceroute", "routing_table", "netstat", "arp_table", "interface_info"]:
            if key in raw_outputs:
                topology_sources[key] = raw_outputs[key]
            elif key in artifacts:
                topology_sources[key] = artifacts[key]

        if include_topology:
            for topo_check in ["routing_table", "arp_table", "interface_info"]:
                if topo_check in topology_sources:
                    continue
                raw = self._collect_if_possible(
                    topo_check,
                    plan,
                    user_prompt,
                    collect_live_stats,
                    allow_config_changes,
                    collection_attempts,
                    collection_errors,
                )
                if raw:
                    topology_sources[topo_check] = raw
                    raw_outputs[topo_check] = raw
                    parsed[topo_check] = {"present": True}

        topology = parse_topology_snapshot(topology_sources, plan.host_os) if include_topology else {}

        return ExecutionResult(
            raw_outputs=raw_outputs,
            parsed_outputs=parsed,
            executed_checks=list(raw_outputs.keys()),
            missing_checks=missing_checks,
            host_os=plan.host_os,
            network_topology=topology,
            collection_attempts=collection_attempts,
            collection_errors=collection_errors,
        )
