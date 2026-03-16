from network_agent.agents.validator import Validator
from network_agent.core.host_os import HostOS
from network_agent.core.safety import SafetyGate
from network_agent.core.schemas import CandidateCause, Diagnosis, ExecutionResult


def test_validator_blocks_forbidden_command() -> None:
    validator = Validator(safety_gate=SafetyGate.default(host_os=HostOS.LINUX))
    diagnosis = Diagnosis(
        problem_summary="x",
        candidate_causes_ranked=[
            CandidateCause(title="c", confidence=0.7, required_evidence=["a"], remediation_steps=["b"])
        ],
        confidence_score=0.7,
        required_evidence=["a"],
        remediation_plan=["b"],
    )
    execution = ExecutionResult(
        raw_outputs={"ping": "ok"},
        parsed_outputs={"ping": {"packet_loss_pct": 0}},
        executed_checks=["ping"],
        missing_checks=[],
        host_os=HostOS.LINUX,
    )
    result = validator.validate(diagnosis, execution, proposed_commands=["rm -rf /", "ping 8.8.8.8"])
    assert not result.valid
    assert result.blocked_operations == ["rm -rf /"]
    assert result.needs_user_confirmation
    assert result.confirmation_question


def test_windows_whitelist_accepts_tracert() -> None:
    gate = SafetyGate.default(host_os=HostOS.WINDOWS)
    allowed, reason = gate.is_allowed("tracert 8.8.8.8")
    assert allowed
    assert reason is None


def test_validator_requires_approval_for_mutating_command() -> None:
    validator = Validator(safety_gate=SafetyGate.default(host_os=HostOS.LINUX))
    diagnosis = Diagnosis(
        problem_summary="x",
        candidate_causes_ranked=[
            CandidateCause(title="c", confidence=0.7, required_evidence=["a"], remediation_steps=["b"])
        ],
        confidence_score=0.7,
        required_evidence=["a"],
        remediation_plan=["b"],
    )
    execution = ExecutionResult(
        raw_outputs={"ping": "ok"},
        parsed_outputs={"ping": {"packet_loss_pct": 0}},
        executed_checks=["ping"],
        missing_checks=[],
        host_os=HostOS.LINUX,
    )
    proposed = ["route add default gw 10.0.0.1", "netstat -an"]
    blocked = validator.validate(diagnosis, execution, proposed_commands=proposed)
    assert not blocked.valid
    assert blocked.blocked_operations == ["route add default gw 10.0.0.1"]

    approved = validator.validate(
        diagnosis,
        execution,
        proposed_commands=proposed,
        approved_commands={"route add default gw 10.0.0.1"},
    )
    assert approved.valid


def test_validator_closes_chat_after_user_confirmation() -> None:
    validator = Validator(safety_gate=SafetyGate.default(host_os=HostOS.LINUX))
    diagnosis = Diagnosis(
        problem_summary="x",
        candidate_causes_ranked=[
            CandidateCause(title="c", confidence=0.7, required_evidence=["a"], remediation_steps=["b"])
        ],
        confidence_score=0.7,
        required_evidence=["a"],
        remediation_plan=["b"],
    )
    execution = ExecutionResult(
        raw_outputs={"ping": "ok"},
        parsed_outputs={"ping": {"packet_loss_pct": 0}},
        executed_checks=["ping"],
        missing_checks=[],
        host_os=HostOS.LINUX,
    )
    result = validator.validate(diagnosis, execution, user_issue_stopped=True)
    assert result.chat_should_close
    assert not result.needs_user_confirmation
    assert "closing this troubleshooting chat" in result.resolved_acknowledgement
