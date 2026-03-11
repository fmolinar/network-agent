from __future__ import annotations

from network_agent.core.schemas import CandidateCause, Category, Diagnosis, ExecutionResult, PlannerPlan


class Generator:
    def generate(self, plan: PlannerPlan, user_prompt: str, execution: ExecutionResult) -> Diagnosis:
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
        return Diagnosis(
            problem_summary=f"Category={plan.category.value} HostOS={plan.host_os.value}. {user_prompt.strip()}",
            candidate_causes_ranked=causes,
            confidence_score=top_conf,
            required_evidence=sorted({e for c in causes for e in c.required_evidence}),
            remediation_plan=causes[0].remediation_steps,
            metadata={
                "selected_checks": plan.selected_checks,
                "executed_checks": execution.executed_checks,
                "missing_checks": execution.missing_checks,
                "host_os": plan.host_os.value,
            },
        )
