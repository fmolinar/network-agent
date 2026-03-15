# LLM and Tool Call Sequence

## End-to-End Sequence

```mermaid
sequenceDiagram
    participant User
    participant Planner
    participant Executor
    participant Generator
    participant Validator
    participant LLM as Optional LLMs

    User->>Planner: prompt + artifacts
    Planner->>LLM: planner prompt (optional)
    LLM-->>Planner: category + selected checks (JSON)
    Planner-->>Executor: PlannerPlan

    Executor->>Executor: parse provided artifacts
    Executor->>Executor: run whitelisted commands for missing checks (optional)
    Executor-->>Generator: ExecutionResult

    Generator->>LLM: generator prompt (optional)
    LLM-->>Generator: diagnosis payload (JSON)
    Generator-->>Validator: Diagnosis + ExecutionResult

    Validator->>LLM: critic prompt (conditional)
    LLM-->>Validator: accept/caution/reject (JSON)
    Validator-->>User: final result bundle
```

## Intermediate Representations
1. `PlannerPlan`
   - category
   - selected checks
   - rationale
   - host_os

2. `ExecutionResult`
   - raw outputs
   - parsed outputs
   - executed/missing checks
   - topology snapshot
   - collection attempts/errors

3. `Diagnosis`
   - problem summary
   - ranked causes + confidence
   - required evidence
   - remediation plan

4. `ValidationResult`
   - valid flag
   - reasons
   - blocked operations
   - optional critic verdict

## Prompt Roles
- Planner prompt: triage and check selection.
- Generator prompt: evidence-grounded hypothesis generation.
- Validator critic prompt: consistency and evidence sufficiency check.

## Tool Calls
- Safe shell diagnostics only (allowlisted by OS).
- Packet capture (`tcpdump`) is time bounded by capture duration controls.
- No destructive operations permitted without explicit approval path.
