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
from network_agent.core.host_os import parse_host_os
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

    def run(
        self,
        user_prompt: str,
        artifacts: dict[str, str],
        collect_live_stats: bool = False,
        allow_config_changes: bool = False,
        capture_seconds: int = 30,
        include_topology: bool = True,
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

        val_t0, val_entry = _op_start(
            "validator",
            "validate",
            {"use_llm_critic": use_llm_critic, "confidence_score": diagnosis.confidence_score},
        )
        validation = self.validator.validate(diagnosis, execution, use_llm_critic=use_llm_critic)
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
            validator_system, validator_user = validator_prompt(diagnosis, execution)
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
