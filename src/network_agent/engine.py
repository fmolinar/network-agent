from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path
import time
from typing import Any
import uuid

from network_agent.agents.executor import Executor
from network_agent.agents.generator import Generator
from network_agent.agents.planner import Planner
from network_agent.agents.prompts import generator_prompt, planner_prompt, validator_prompt
from network_agent.agents.validator import Validator
from network_agent.core.agent_llm import AgentLLMConfig, AgentLLMConnector
from network_agent.core.audit import AuditLogger
from network_agent.core.host_os import HostOS, parse_host_os
from network_agent.core.llm import LLMCritic, LLMConfig
from network_agent.core.safety import SafetyGate
from network_agent.tools.network_checks import WhitelistedShellRunner


class NetworkTroubleshootingEngine:
    def __init__(
        self,
        audit_path: str = "artifacts/audit.log",
        host_os: str | None = None,
        llm_config: LLMConfig | None = None,
        agent_llm_config: AgentLLMConfig | None = None,
    ) -> None:
        self.host_os = parse_host_os(host_os)
        self.safety_gate = SafetyGate.default(host_os=self.host_os)
        self.llm_config = llm_config or LLMConfig.from_env()
        self.agent_llm_config = agent_llm_config or AgentLLMConfig.from_env()
        self.agent_llm_connector = (
            AgentLLMConnector(self.agent_llm_config)
            if self.agent_llm_config.provider.lower() not in {"", "none"}
            else None
        )
        self.planner = Planner(llm_connector=self.agent_llm_connector)
        self.executor = Executor(runner=WhitelistedShellRunner(safety_gate=self.safety_gate))
        self.generator = Generator(llm_connector=self.agent_llm_connector)
        self.validator = Validator(safety_gate=self.safety_gate, llm_critic=LLMCritic(self.llm_config))
        self.audit = AuditLogger(path=Path(audit_path))

    def _command_artifact_key(self, command: str, host_os: HostOS) -> str | None:
        parts = command.strip().split()
        if not parts:
            return None
        head = parts[0].lower()
        if head == "ping":
            return "ping"
        if head in {"traceroute", "tracert"}:
            return "traceroute"
        if head in {"nslookup", "dig"}:
            return "dns_trace"
        if head == "netstat":
            return "netstat"
        if head == "route":
            return "routing_table"
        if head == "arp":
            return "arp_table"
        if head in {"ipconfig", "ifconfig", "ip"}:
            return "interface_info"
        if head == "tcpdump" and host_os != HostOS.WINDOWS:
            return "pcap_summary"
        return None

    def _execute_proposed_commands(
        self,
        commands: list[str],
        host_os: HostOS,
        allow_config_changes: bool,
        capture_seconds: int,
    ) -> tuple[dict[str, str], dict[str, Any]]:
        trace: dict[str, Any] = {"attempted": commands, "ran": [], "blocked": [], "errors": {}}
        artifacts: dict[str, str] = {}
        runner = self.executor.runner
        if runner is None:
            trace["errors"]["runner"] = "live runner not configured"
            return artifacts, trace

        for command in commands:
            cmd = command.strip()
            if not cmd:
                continue
            allowed, reason = self.safety_gate.check_command(cmd, user_approved=allow_config_changes)
            if not allowed:
                trace["blocked"].append(cmd)
                trace["errors"][cmd] = reason or "command blocked"
                continue

            parts = cmd.split()
            head = parts[0].lower() if parts else ""
            timeout_override = capture_seconds + 3 if head == "tcpdump" else None
            try:
                output = runner.run(cmd, user_approved=allow_config_changes, timeout_seconds=timeout_override)
            except Exception as exc:  # noqa: BLE001
                trace["errors"][cmd] = str(exc)
                continue

            trace["ran"].append(cmd)
            artifact_key = self._command_artifact_key(cmd, host_os)
            if artifact_key and output:
                artifacts[artifact_key] = output

        return artifacts, trace

    def run(
        self,
        user_prompt: str,
        artifacts: dict[str, str],
        collect_live_stats: bool = False,
        allow_config_changes: bool = False,
        capture_seconds: int = 30,
        execute_proposed_commands: bool = True,
        include_topology: bool = True,
        user_issue_stopped: bool | None = None,
        use_llm_critic: bool = False,
        capture_agent_prompts: bool = False,
        debug: bool = False,
    ) -> dict[str, Any]:
        req_id = str(uuid.uuid4())
        started = time.perf_counter()
        started_ts = datetime.now(timezone.utc).isoformat()
        debug_ops: list[dict[str, Any]] = []

        def _op_start(agent: str, operation: str, payload: dict[str, Any]) -> tuple[float, dict[str, Any]]:
            t0 = time.perf_counter()
            entry = {
                "agent": agent,
                "operation": operation,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "input": payload,
            }
            return t0, entry

        def _op_end(t0: float, entry: dict[str, Any], output: dict[str, Any]) -> None:
            entry["finished_at"] = datetime.now(timezone.utc).isoformat()
            entry["duration_ms"] = round((time.perf_counter() - t0) * 1000, 3)
            entry["output"] = output
            debug_ops.append(entry)

        plan_t0, plan_entry = _op_start(
            "planner",
            "plan",
            {"user_prompt": user_prompt, "artifact_keys": sorted(artifacts.keys()), "host_os": self.host_os.value},
        )
        plan = self.planner.plan(user_prompt, artifacts, host_os=self.host_os)
        self.audit.log("planner.plan", asdict(plan))
        _op_end(plan_t0, plan_entry, asdict(plan))

        exec_t0, exec_entry = _op_start(
            "executor",
            "run",
            {
                "selected_checks": plan.selected_checks,
                "collect_live_stats": collect_live_stats,
                "allow_config_changes": allow_config_changes,
                "capture_seconds": capture_seconds,
                "include_topology": include_topology,
            },
        )
        execution = self.executor.run(
            plan,
            artifacts,
            user_prompt=user_prompt,
            collect_live_stats=collect_live_stats,
            allow_config_changes=allow_config_changes,
            capture_seconds=capture_seconds,
            include_topology=include_topology,
        )
        self.audit.log("executor.run", asdict(execution))
        _op_end(
            exec_t0,
            exec_entry,
            {
                "executed_checks": execution.executed_checks,
                "missing_checks": execution.missing_checks,
                "collection_attempts": execution.collection_attempts,
                "collection_errors": execution.collection_errors,
                "network_topology": execution.network_topology,
            },
        )

        gen_t0, gen_entry = _op_start(
            "generator",
            "generate",
            {"category": plan.category.value, "executed_checks": execution.executed_checks},
        )
        diagnosis = self.generator.generate(plan, user_prompt, execution)
        self.audit.log("generator.generate", asdict(diagnosis))
        _op_end(gen_t0, gen_entry, asdict(diagnosis))

        command_trace: dict[str, Any] = {"attempted": [], "ran": [], "blocked": [], "errors": {}}
        proposed_commands = diagnosis.metadata.get("proposed_commands", [])
        if not isinstance(proposed_commands, list):
            proposed_commands = []
        proposed_commands = [str(c).strip() for c in proposed_commands if str(c).strip()]

        if execute_proposed_commands and collect_live_stats and proposed_commands:
            cmd_t0, cmd_entry = _op_start(
                "executor",
                "run_proposed_commands",
                {"proposed_commands": proposed_commands, "capture_seconds": capture_seconds},
            )
            extra_artifacts, command_trace = self._execute_proposed_commands(
                proposed_commands,
                self.host_os,
                allow_config_changes=allow_config_changes,
                capture_seconds=capture_seconds,
            )
            cmd_entry_output = {
                "ran": command_trace.get("ran", []),
                "blocked": command_trace.get("blocked", []),
                "errors": command_trace.get("errors", {}),
                "artifact_keys": sorted(extra_artifacts.keys()),
            }
            _op_end(cmd_t0, cmd_entry, cmd_entry_output)
            self.audit.log("executor.run_proposed_commands", cmd_entry_output)

            if extra_artifacts:
                merged_artifacts = dict(artifacts)
                merged_artifacts.update(execution.raw_outputs)
                merged_artifacts.update(extra_artifacts)
                execution = self.executor.run(
                    plan,
                    merged_artifacts,
                    user_prompt=user_prompt,
                    collect_live_stats=False,
                    allow_config_changes=allow_config_changes,
                    capture_seconds=capture_seconds,
                    include_topology=include_topology,
                )
                self.audit.log("executor.run_after_proposed_commands", asdict(execution))

                regen_t0, regen_entry = _op_start(
                    "generator",
                    "generate_after_proposed_commands",
                    {"executed_checks": execution.executed_checks},
                )
                diagnosis = self.generator.generate(plan, user_prompt, execution)
                _op_end(regen_t0, regen_entry, asdict(diagnosis))
                self.audit.log("generator.generate_after_proposed_commands", asdict(diagnosis))

            commands_ran = command_trace.get("ran", [])
            commands_blocked = command_trace.get("blocked", [])
            diagnosis.metadata["commands_attempted"] = proposed_commands
            diagnosis.metadata["commands_ran"] = commands_ran
            diagnosis.metadata["commands_blocked"] = commands_blocked
            diagnosis.metadata["command_errors"] = command_trace.get("errors", {})
            logic = diagnosis.metadata.get("command_logic")
            if not logic:
                checks = ", ".join(execution.executed_checks[:4]) if execution.executed_checks else "none"
                logic = f"Compared outputs from executed checks ({checks}) to rank the top cause."
                diagnosis.metadata["command_logic"] = logic

        val_t0, val_entry = _op_start(
            "validator",
            "validate",
            {
                "use_llm_critic": use_llm_critic,
                "confidence_score": diagnosis.confidence_score,
                "proposed_commands": diagnosis.metadata.get("proposed_commands", []),
                "user_issue_stopped": user_issue_stopped,
            },
        )
        proposed_commands = diagnosis.metadata.get("proposed_commands", [])
        if not isinstance(proposed_commands, list):
            proposed_commands = []
        validation = self.validator.validate(
            diagnosis,
            execution,
            proposed_commands=[str(c) for c in proposed_commands if str(c).strip()],
            user_issue_stopped=user_issue_stopped,
            use_llm_critic=use_llm_critic,
        )
        self.audit.log("validator.validate", asdict(validation))
        _op_end(val_t0, val_entry, asdict(validation))

        result = {
            "plan": asdict(plan),
            "diagnosis": asdict(diagnosis),
            "validation": asdict(validation),
            "execution": asdict(execution),
        }
        if capture_agent_prompts:
            planner_system, planner_user = planner_prompt(user_prompt, artifacts, self.host_os.value)
            generator_system, generator_user = generator_prompt(plan, user_prompt, execution)
            validator_system, validator_user = validator_prompt(diagnosis, execution, user_issue_stopped=user_issue_stopped)
            result["agent_prompts"] = {
                "planner": {"system": planner_system, "user": planner_user},
                "generator": {"system": generator_system, "user": generator_user},
                "validator": {"system": validator_system, "user": validator_user},
            }

        if debug:
            result["debug"] = {
                "request_id": req_id,
                "started_at": started_ts,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "host_os": self.host_os.value,
                "agent_operations": debug_ops,
            }

        return result
