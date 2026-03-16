# Prompt Templates

This project uses role-specific prompt templates from `src/network_agent/agents/prompts.py`.

## Planner Template

### System
- Role: PlannerAgent for network troubleshooting.
- Task: classify incident and choose checks.
- Output schema: `category`, `selected_checks`, `rationale`.

### User payload
- `host_os`
- raw `user_prompt`
- compact artifact preview

## Generator Template

### System
- Role: GeneratorAgent for network troubleshooting.
- Task: produce diagnosis JSON.
- Output schema:
  - `problem_summary`
  - `candidate_causes_ranked`
  - `confidence_score`
  - `required_evidence`
  - `remediation_plan`

### User payload
- plan context (`category`, `selected_checks`, `host_os`)
- parsed execution outputs
- missing checks
- topology snapshot

## Validator Critic Template

### System
- Role: ValidatorAgent for consistency/safety review.
- Task: issue verdict on diagnosis quality and handle resolution confirmation flow.
- Output schema:
  - `verdict` (`accept`, `caution`, `reject`)
  - `confidence`
  - `issue_resolved_likely`
  - `needs_user_confirmation`
  - `confirmation_question`
  - `close_chat`
  - `closure_acknowledgement`
  - `notes`
  - `suggested_evidence`

### User payload
- diagnosis summary and ranked causes
- execution context and topology
- optional `user_issue_stopped` confirmation signal (`true`, `false`, or `null`)

## Design Notes
- All templates request strict JSON to reduce parsing ambiguity.
- LLM outputs are normalized and validated before acceptance.
- Invalid or empty LLM outputs trigger deterministic fallback paths.
