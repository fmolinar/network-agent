# Documentation

This folder contains architecture and extension guidance for `network-agent`.

## Design Principles
- Safety-first execution model
- Deterministic validation before any suggestion is trusted
- Traceability via audit logs
- Incremental, testable parsers and diagnosis rules
- Platform-aware behavior for macOS/Linux/Windows

## Diagnosis Contract
Every diagnosis object must include:
- `problem_summary`
- `candidate_causes_ranked` (with confidence)
- `confidence_score` in `[0, 1]`
- `required_evidence`
- `remediation_plan`

## Safety Contract
- Executor defaults to read-only diagnostics
- Commands must pass whitelist + forbidden-token checks
- Whitelist must be selected by host OS profile
- Any action that changes config requires explicit user approval

## OS-Aware Handling
- Detect host platform automatically (`auto`) or allow explicit override
- Normalize platform command differences (`traceroute` vs `tracert`)
- Keep parser inputs platform-neutral where possible

## CI & Lab Validation
- Cross-platform unit tests run in GitHub Actions on Linux/macOS/Windows.
- Docker Compose lab creates reproducible Linux network scenarios and exports artifacts to `samples/generated/`.
- Curated static fixtures in `samples/` are used for deterministic regression tests.

## Live Collection Mode
- Engine/CLI can attempt live collection for missing evidence (`ping`, `traceroute/tracert`, `netstat`, `nslookup`, and `tcpdump` where available).
- Collection attempts and errors are captured in execution metadata for auditability.
- If a command implies a configuration change, it is blocked unless approval is explicitly provided.

## LLM Critic
- Validator can call an optional LLM critic only for ambiguous cases.
- LLM verdicts are advisory and captured in `validation.llm_critic`.
- Safety gate decisions remain authoritative regardless of LLM output.
- Provider adapters currently supported:
  - OpenAI Chat Completions
  - Anthropic Messages
  - Ollama chat API
  - Mock local critic for test/dev environments

## Topology Output
- Executor generates a host-view topology summary in `execution.network_topology`.
- Source inputs include traceroute hops, routing tables, ARP entries, and interface snapshots.
- This helps users understand local gateway visibility, path shape, and neighbor discovery context.

## Request Debug Mode
- Engine supports request-scoped debug traces for all agents.
- Trace includes: planner, executor, generator, validator operations with inputs, outputs, and timings.
- CLI flags:
  - `--debug` to include trace in response
  - `--debug-output <path>` to save trace JSON for offline evaluation

## Extension Guide
1. Add new parser in `src/network_agent/parsers/`
2. Register parser use path in `Executor`
3. Add scoring/evidence rules in `Generator`
4. Add validation thresholds in `Validator`
5. Update OS-specific whitelist or aliases if needed
6. Add synthetic test case in `tests/`

## Synthetic Case Ideas
- DNS NXDOMAIN with working ICMP to resolver
- Last-hop traceroute timeout with high packet loss
- TLS failures with valid route and low loss
- High retransmits with no DNS/routing errors
- Windows-only `tracert` artifact with route degradation
