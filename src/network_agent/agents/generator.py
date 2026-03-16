from __future__ import annotations

from network_agent.agents.prompts import generator_prompt
from network_agent.core.agent_llm import AgentLLMConnector
from network_agent.core.schemas import CandidateCause, Category, Diagnosis, ExecutionResult, PlannerPlan


class Generator:
    def __init__(self, llm_connector: AgentLLMConnector | None = None) -> None:
        self.llm_connector = llm_connector

    def _clamp_confidence(self, value: object, default: float) -> float:
        if isinstance(value, (int, float)):
            return float(max(0.0, min(1.0, value)))
        return default

    def _parse_proposed_commands(self, value: object) -> list[str]:
        commands: list[str] = []
        if not isinstance(value, list):
            return commands
        for item in value:
            cmd_text = ""
            if isinstance(item, str):
                cmd_text = item.strip()
            elif isinstance(item, dict):
                # Accept either {"command": "..."} or {"cmd": "..."} payload shapes.
                cmd_text = str(item.get("command") or item.get("cmd") or "").strip()
            if cmd_text:
                commands.append(cmd_text)
        return commands[:10]

    def _build_logic_summary(self, commands: list[str], execution: ExecutionResult) -> str:
        evidence = execution.executed_checks[:4]
        if commands:
            return (
                f"Used command evidence from {', '.join(commands[:4])}; "
                f"cross-checked against parsed checks {', '.join(evidence) if evidence else 'none'}."
            )
        return f"Derived from parsed checks {', '.join(evidence) if evidence else 'none'}."

    def _plain_explanation(self, top_cause: str, remediation: list[str]) -> str:
        first_step = remediation[0] if remediation else "collect one more round of network checks"
        return (
            f"In simple terms: the most likely issue is '{top_cause}'. "
            f"Start with this action: {first_step}."
        )

    def _default_proposed_commands(self, plan: PlannerPlan) -> list[str]:
        by_category = {
            Category.CONNECTIVITY: ["ping 8.8.8.8", "traceroute 8.8.8.8"],
            Category.DNS: ["nslookup example.com", "ping 1.1.1.1"],
            Category.ROUTING: ["traceroute 8.8.8.8", "netstat -rn"],
            Category.TRANSPORT: ["netstat -an", "tcpdump -nn"],
            Category.SECURITY: ["netstat -an", "ping 8.8.8.8"],
            Category.UNKNOWN: ["ping 8.8.8.8", "traceroute 8.8.8.8"],
        }
        windows_by_category = {
            Category.CONNECTIVITY: ["ping 8.8.8.8", "tracert 8.8.8.8"],
            Category.DNS: ["nslookup example.com", "ping 1.1.1.1"],
            Category.ROUTING: ["tracert 8.8.8.8", "route print"],
            Category.TRANSPORT: ["netstat -an", "ping 8.8.8.8"],
            Category.SECURITY: ["netstat -an", "ping 8.8.8.8"],
            Category.UNKNOWN: ["ping 8.8.8.8", "tracert 8.8.8.8"],
        }
        if plan.host_os.value == "windows":
            return windows_by_category.get(plan.category, windows_by_category[Category.UNKNOWN])
        commands = by_category.get(plan.category, by_category[Category.UNKNOWN])
        return commands

    def _llm_generate(self, plan: PlannerPlan, user_prompt: str, execution: ExecutionResult) -> Diagnosis | None:
        if self.llm_connector is None:
            return None
        system, user = generator_prompt(plan, user_prompt, execution)
        llm_diag = self.llm_connector.ask_json(system, user, task="generator")
        causes_raw = llm_diag.get("candidate_causes_ranked", [])
        if not isinstance(causes_raw, list) or not causes_raw:
            return None

        causes: list[CandidateCause] = []
        for item in causes_raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            confidence = self._clamp_confidence(item.get("confidence"), 0.4)
            required_evidence = item.get("required_evidence", [])
            remediation_steps = item.get("remediation_steps", [])
            required_evidence = [str(v) for v in required_evidence] if isinstance(required_evidence, list) else []
            remediation_steps = [str(v) for v in remediation_steps] if isinstance(remediation_steps, list) else []
            if not required_evidence:
                required_evidence = ["parsed_outputs"]
            if not remediation_steps:
                remediation_steps = ["Collect additional network evidence and rerun diagnosis"]
            causes.append(
                CandidateCause(
                    title=title,
                    confidence=confidence,
                    required_evidence=required_evidence,
                    remediation_steps=remediation_steps,
                )
            )
        if not causes:
            return None

        causes.sort(key=lambda c: c.confidence, reverse=True)
        confidence_score = self._clamp_confidence(llm_diag.get("confidence_score"), causes[0].confidence)
        required_evidence = llm_diag.get("required_evidence", [])
        if not isinstance(required_evidence, list) or not required_evidence:
            required_evidence = sorted({e for c in causes for e in c.required_evidence})
        remediation_plan = llm_diag.get("remediation_plan", [])
        if not isinstance(remediation_plan, list) or not remediation_plan:
            remediation_plan = causes[0].remediation_steps
        proposed_commands = self._parse_proposed_commands(llm_diag.get("proposed_commands", []))
        logic_summary = str(llm_diag.get("command_logic") or self._build_logic_summary(proposed_commands, execution))
        plain_explanation = str(llm_diag.get("plain_explanation") or self._plain_explanation(causes[0].title, [str(v) for v in remediation_plan]))
        problem_summary = str(
            llm_diag.get("problem_summary") or f"Category={plan.category.value} HostOS={plan.host_os.value}. {user_prompt.strip()}"
        )
        return Diagnosis(
            problem_summary=problem_summary,
            candidate_causes_ranked=causes,
            confidence_score=confidence_score,
            required_evidence=[str(v) for v in required_evidence],
            remediation_plan=[str(v) for v in remediation_plan],
            metadata={
                "selected_checks": plan.selected_checks,
                "executed_checks": execution.executed_checks,
                "missing_checks": execution.missing_checks,
                "host_os": plan.host_os.value,
                "generation_mode": "llm",
                "proposed_commands": proposed_commands,
                "command_logic": logic_summary,
                "user_explanation": plain_explanation,
            },
        )

    def _heuristic_generate(self, plan: PlannerPlan, user_prompt: str, execution: ExecutionResult) -> Diagnosis:
        causes: list[CandidateCause] = []
        top_conf = 0.4

        ping = execution.parsed_outputs.get("ping", {})
        trace = execution.parsed_outputs.get("traceroute", {})
        logs = execution.parsed_outputs.get("logs", {})
        pcap = execution.parsed_outputs.get("pcap_summary", {})

        if plan.category == Category.CONNECTIVITY:
            loss = float(ping.get("packet_loss_pct", 0.0))
            if loss >= 50:
                top_conf = 0.85
                causes.append(
                    CandidateCause(
                        title="High packet loss indicates unstable or broken link",
                        confidence=0.85,
                        required_evidence=["packet_loss_pct", "traceroute timeouts"],
                        remediation_steps=[
                            "Check physical link/Wi-Fi signal and interface errors",
                            "Restart local gateway/router",
                            "Test from another host to isolate host vs network",
                        ],
                    )
                )

        if plan.category == Category.DNS or logs.get("dns_failure"):
            top_conf = max(top_conf, 0.82)
            causes.append(
                CandidateCause(
                    title="DNS resolution failure",
                    confidence=0.82,
                    required_evidence=["logs.dns_failure", "resolver config"],
                    remediation_steps=[
                        "Validate resolver settings (platform-specific DNS config)",
                        "Try alternate resolvers (1.1.1.1, 8.8.8.8)",
                        "Flush DNS cache and retry",
                    ],
                )
            )

        if trace.get("timeout_ratio", 0) > 0.4:
            top_conf = max(top_conf, 0.78)
            causes.append(
                CandidateCause(
                    title="Upstream routing path instability",
                    confidence=0.78,
                    required_evidence=["traceroute.timeout_ratio", "gateway metrics"],
                    remediation_steps=[
                        "Check gateway health and route advertisements",
                        "Review ISP/upstream incidents",
                        "Force alternate route if available",
                    ],
                )
            )

        if pcap.get("retransmits", 0) and pcap.get("retransmits", 0) > 20:
            top_conf = max(top_conf, 0.74)
            causes.append(
                CandidateCause(
                    title="Transport congestion or drops causing retransmissions",
                    confidence=0.74,
                    required_evidence=["pcap.retransmits", "interface drops"],
                    remediation_steps=[
                        "Inspect interface drop counters and duplex mismatches",
                        "Reduce queue pressure/QoS misconfiguration",
                        "Tune TCP settings after root cause isolation",
                    ],
                )
            )

        if logs.get("tls_error") or logs.get("auth_block"):
            top_conf = max(top_conf, 0.76)
            causes.append(
                CandidateCause(
                    title="Security policy/TLS issue blocking traffic",
                    confidence=0.76,
                    required_evidence=["logs.tls_error or logs.auth_block", "policy rules"],
                    remediation_steps=[
                        "Validate certificate chain/time sync",
                        "Review firewall/policy denies for destination",
                        "Whitelist expected endpoints if policy permits",
                    ],
                )
            )

        if not causes:
            causes.append(
                CandidateCause(
                    title="Insufficient evidence for specific root cause",
                    confidence=0.4,
                    required_evidence=["ping", "traceroute", "logs", "pcap_summary"],
                    remediation_steps=[
                        "Collect full ping/traceroute outputs",
                        "Attach relevant system/network logs",
                        "Provide packet capture summary with key counters",
                    ],
                )
            )

        causes.sort(key=lambda c: c.confidence, reverse=True)
        proposed_commands = self._default_proposed_commands(plan)
        remediation_plan = causes[0].remediation_steps
        return Diagnosis(
            problem_summary=f"Category={plan.category.value} HostOS={plan.host_os.value}. {user_prompt.strip()}",
            candidate_causes_ranked=causes,
            confidence_score=top_conf,
            required_evidence=sorted({e for c in causes for e in c.required_evidence}),
            remediation_plan=remediation_plan,
            metadata={
                "selected_checks": plan.selected_checks,
                "executed_checks": execution.executed_checks,
                "missing_checks": execution.missing_checks,
                "host_os": plan.host_os.value,
                "generation_mode": "heuristic",
                "proposed_commands": proposed_commands,
                "command_logic": self._build_logic_summary(proposed_commands, execution),
                "user_explanation": self._plain_explanation(causes[0].title, remediation_plan),
            },
        )

    def generate(self, plan: PlannerPlan, user_prompt: str, execution: ExecutionResult) -> Diagnosis:
        llm_result = self._llm_generate(plan, user_prompt, execution)
        if llm_result is not None:
            return llm_result
        return self._heuristic_generate(plan, user_prompt, execution)
