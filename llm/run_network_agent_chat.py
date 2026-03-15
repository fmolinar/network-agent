#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]


def _python_bin() -> str:
    if os.name == "nt":
        candidate = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
        if candidate.exists():
            return str(candidate)
        return "python"
    candidate = ROOT_DIR / ".venv" / "bin" / "python"
    if candidate.exists():
        return str(candidate)
    return "python3"


def _spin_script() -> list[str]:
    if os.name == "nt":
        return ["cmd", "/c", str(ROOT_DIR / "llm" / "spin_llm.bat")]
    return [str(ROOT_DIR / "llm" / "spin_llm.sh")]


def _start_llm(model: str) -> bool:
    if shutil.which("ollama") is None:
        print("Ollama is not installed or unavailable. Program will run manually.")
        return False

    env = os.environ.copy()
    env["NETWORK_AGENT_LOCAL_MODEL"] = model
    command = _spin_script() + [model]
    proc = subprocess.run(
        command,
        cwd=ROOT_DIR,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        print("Could not start local LLM cleanly. Program will run manually.")
        return False

    print("Local LLM is ready.")
    return True


def _runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(ROOT_DIR / "src")
    existing = env.get("PYTHONPATH", "").strip()
    if existing:
        env["PYTHONPATH"] = f"{src_path}{os.pathsep}{existing}"
    else:
        env["PYTHONPATH"] = src_path
    return env


def _format_reply(payload: dict[str, Any]) -> str:
    diagnosis = payload.get("diagnosis", {})
    validation = payload.get("validation", {})
    causes = diagnosis.get("candidate_causes_ranked", [])
    top = causes[0] if isinstance(causes, list) and causes else {}

    lines = [
        f"Summary: {diagnosis.get('problem_summary', 'n/a')}",
        f"Top cause: {top.get('title', 'n/a')}",
        f"Confidence: {diagnosis.get('confidence_score', 'n/a')}",
    ]

    remediation = diagnosis.get("remediation_plan", [])
    if isinstance(remediation, list) and remediation:
        lines.append("Remediation:")
        lines.extend(f"- {step}" for step in remediation[:3])

    reasons = validation.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        lines.append("Validation notes:")
        lines.extend(f"- {reason}" for reason in reasons)

    return "\n".join(lines)


def main() -> int:
    model = os.getenv("NETWORK_AGENT_LOCAL_MODEL", "llama3.2")
    host = os.getenv("OLLAMA_HOST", "127.0.0.1:11434")
    py = _python_bin()
    use_llm_agents = _start_llm(model)

    print("\nNetwork Agent Chat CLI")
    print("Type your network issue and press Enter.")
    print("Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            issue = input("You> ").strip()
        except EOFError:
            print("\nExiting.")
            return 0

        if not issue:
            continue
        if issue.lower() in {"exit", "quit"}:
            print("Exiting.")
            return 0

        cmd = [
            py,
            "-m",
            "network_agent.cli",
            "--prompt",
            issue,
            "--host-os",
            "auto",
            "--collect-live-stats",
        ]
        if use_llm_agents:
            cmd.extend(
                [
                    "--enable-llm-agents",
                    "--agent-llm-provider",
                    "ollama",
                    "--agent-llm-model",
                    model,
                    "--agent-llm-base-url",
                    f"http://{host}/api/chat",
                ]
            )

        proc = subprocess.run(
            cmd,
            cwd=ROOT_DIR,
            env=_runtime_env(),
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            print("Agent> Execution failed.")
            if proc.stderr.strip():
                print(f"Agent> {proc.stderr.strip()}")
            continue

        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            print("Agent> Invalid JSON response from network-agent.")
            continue

        print("Agent>")
        print(_format_reply(payload))
        print()


if __name__ == "__main__":
    sys.exit(main())
