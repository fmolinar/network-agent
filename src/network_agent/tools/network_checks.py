from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass

from network_agent.core.safety import SafetyGate


@dataclass(slots=True)
class WhitelistedShellRunner:
    safety_gate: SafetyGate
    timeout_seconds: int = 20

    def run(self, command: str, user_approved: bool = False) -> str:
        allowed, reason = self.safety_gate.check_command(command, user_approved=user_approved)
        if not allowed:
            raise ValueError(f"blocked by safety gate: {reason}")

        proc = subprocess.run(
            shlex.split(command),
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        return (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
