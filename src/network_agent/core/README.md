# Core

## `schemas.py`
Typed dataclasses for plans, diagnosis, execution outputs (including topology snapshot), and validation results.

## `host_os.py`
Host platform detection and parsing (`macos`, `linux`, `windows`, `unknown`).

## `llm.py`
Optional LLM critic adapters and shared config loader (`mock`, `openai`, `anthropic`, `ollama`).

## `safety.py`
Safety gate with OS-aware command allowlist, forbidden token checks, and approval requirements for config-changing commands.

## `audit.py`
JSONL event logger for agent pipeline traceability.
