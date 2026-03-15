from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass

from network_agent.core.safety import SafetyGate


@dataclass(slots=True)
class WhitelistedShellRunner:
    safety_gate: SafetyGate
    timeout_seconds: int = 20

    def run(self, command: str, user_approved: bool = False, timeout_seconds: int | None = None) -> str:
        allowed, reason = self.safety_gate.check_command(command, user_approved=user_approved)
        if not allowed:
            raise ValueError(f"blocked by safety gate: {reason}")

        effective_timeout = timeout_seconds if timeout_seconds is not None else self.timeout_seconds
        try:
            proc = subprocess.run(
                shlex.split(command),
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                check=False,
            )
            return (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            return (stdout or "") + ("\n" + stderr if stderr else "")
