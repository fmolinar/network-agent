from __future__ import annotations

from dataclasses import dataclass

from network_agent.core.llm import LLMCritic
from network_agent.core.safety import SafetyGate
from network_agent.core.schemas import Diagnosis, ExecutionResult, ValidationResult


@dataclass(slots=True)
class Validator:
    safety_gate: SafetyGate
    llm_critic: LLMCritic | None = None

    def validate(
        self,
        diagnosis: Diagnosis,
        execution: ExecutionResult,
        proposed_commands: list[str] | None = None,
        approved_commands: set[str] | None = None,
        use_llm_critic: bool = False,
    ) -> ValidationResult:
        reasons: list[str] = []
        blocked: list[str] = []
        proposed_commands = proposed_commands or []
        approved_commands = approved_commands or set()

        if not diagnosis.candidate_causes_ranked:
            reasons.append("missing candidate causes")
        if diagnosis.confidence_score < 0.0 or diagnosis.confidence_score > 1.0:
            reasons.append("confidence score out of range")
        if not execution.executed_checks:
            reasons.append("no checks were executed")

        if "ping" in execution.parsed_outputs:
            loss = execution.parsed_outputs["ping"].get("packet_loss_pct")
            if isinstance(loss, (int, float)) and (loss < 0 or loss > 100):
                reasons.append("invalid packet_loss_pct")

        for command in proposed_commands:
            allowed, err = self.safety_gate.check_command(command, user_approved=command in approved_commands)
            if not allowed:
                blocked.append(command)
                reasons.append(err or "command blocked")

        ambiguous = diagnosis.confidence_score < 0.6 or len(diagnosis.required_evidence) > 6
        llm_result: dict[str, object] = {}
        if use_llm_critic and ambiguous and self.llm_critic is not None:
            llm_result = self.llm_critic.critique(
                {
                    "diagnosis": {
                        "problem_summary": diagnosis.problem_summary,
                        "confidence_score": diagnosis.confidence_score,
                        "required_evidence": diagnosis.required_evidence,
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
            )
            verdict = str(llm_result.get("verdict", "")).lower()
            if verdict == "reject":
                reasons.append("llm critic rejected diagnosis consistency/safety")
            elif verdict == "caution":
                reasons.append("llm critic requested additional evidence")

        return ValidationResult(
            valid=not reasons,
            reasons=reasons,
            needs_llm_critic=ambiguous,
            blocked_operations=blocked,
            llm_critic=llm_result,
        )
