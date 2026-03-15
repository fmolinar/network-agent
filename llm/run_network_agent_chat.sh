#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODEL="${NETWORK_AGENT_LOCAL_MODEL:-llama3.1}"
HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Error: Python not found. Install Python 3.10+ to run network-agent."
    exit 1
  fi
fi

USE_LLM_AGENTS="0"

if command -v ollama >/dev/null 2>&1; then
  echo "Local LLM runtime detected (ollama)."
  if "$ROOT_DIR/llm/spin_llm.sh" "$MODEL"; then
    USE_LLM_AGENTS="1"
  else
    echo "Could not start local LLM cleanly. Program will run manually."
  fi
else
  echo "Ollama is not installed or unavailable. Program will run manually."
fi

echo
echo "Network Agent Chat CLI"
echo "Type your network issue and press Enter."
echo "Type 'exit' or 'quit' to stop."
echo

while true; do
  printf "You> "
  IFS= read -r USER_ISSUE || break

  if [[ -z "$USER_ISSUE" ]]; then
    continue
  fi
  if [[ "$USER_ISSUE" == "exit" || "$USER_ISSUE" == "quit" ]]; then
    echo "Exiting."
    break
  fi

  CMD=("$PYTHON_BIN" -m network_agent.cli --prompt "$USER_ISSUE" --host-os auto --collect-live-stats)
  if [[ "$USE_LLM_AGENTS" == "1" ]]; then
    CMD+=(
      --enable-llm-agents
      --agent-llm-provider ollama
      --agent-llm-model "$MODEL"
      --agent-llm-base-url "http://$HOST/api/chat"
    )
  fi

  if ! RAW_JSON="$("${CMD[@]}" 2>/tmp/network-agent-chat.err)"; then
    echo "Agent> Execution failed. Check /tmp/network-agent-chat.err"
    continue
  fi

  echo "Agent>"
  printf "%s\n" "$RAW_JSON" | "$PYTHON_BIN" -c '
import json, sys
payload = json.load(sys.stdin)
diagnosis = payload.get("diagnosis", {})
validation = payload.get("validation", {})
causes = diagnosis.get("candidate_causes_ranked", [])
top = causes[0] if causes else {}

print(f"Summary: {diagnosis.get('problem_summary', 'n/a')}")
print(f"Top cause: {top.get('title', 'n/a')}")
print(f"Confidence: {diagnosis.get('confidence_score', 'n/a')}")

remediation = diagnosis.get("remediation_plan", [])
if remediation:
    print("Remediation:")
    for step in remediation[:3]:
        print(f"- {step}")

if validation.get("reasons"):
    print("Validation notes:")
    for reason in validation.get("reasons", []):
        print(f"- {reason}")
'
  echo
done
