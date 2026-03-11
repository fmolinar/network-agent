from __future__ import annotations

from network_agent.core.host_os import HostOS
from network_agent.core.llm import LLMCritic, LLMConfig
from network_agent.core.safety import SafetyGate
from network_agent.core.schemas import CandidateCause, Diagnosis, ExecutionResult
from network_agent.agents.validator import Validator


def _diag(conf: float) -> Diagnosis:
    return Diagnosis(
        problem_summary="x",
        candidate_causes_ranked=[
            CandidateCause(title="c", confidence=conf, required_evidence=["a"], remediation_steps=["b"])
        ],
        confidence_score=conf,
        required_evidence=["a"],
        remediation_plan=["b"],
    )


def _exec() -> ExecutionResult:
    return ExecutionResult(
        raw_outputs={"ping": "ok"},
        parsed_outputs={"ping": {"packet_loss_pct": 0}},
        executed_checks=["ping"],
        missing_checks=[],
        host_os=HostOS.LINUX,
        network_topology={},
    )


def test_mock_llm_critic_runs_on_ambiguous_case() -> None:
    validator = Validator(
        safety_gate=SafetyGate.default(host_os=HostOS.LINUX),
        llm_critic=LLMCritic(LLMConfig(provider="mock", model="mock-critic")),
    )
    result = validator.validate(_diag(0.4), _exec(), use_llm_critic=True)
    assert result.needs_llm_critic
    assert result.llm_critic
    assert result.llm_critic.get("verdict") in {"accept", "caution", "reject", "error"}


def test_mock_llm_critic_not_used_when_disabled() -> None:
    validator = Validator(
        safety_gate=SafetyGate.default(host_os=HostOS.LINUX),
        llm_critic=LLMCritic(LLMConfig(provider="mock", model="mock-critic")),
    )
    result = validator.validate(_diag(0.4), _exec(), use_llm_critic=False)
    assert result.needs_llm_critic
    assert result.llm_critic == {}
