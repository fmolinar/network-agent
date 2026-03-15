#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import threading
import tkinter as tk
from tkinter import scrolledtext
from tkinter import ttk
from typing import Any


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class NetworkAgentChatGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Network Agent Chat")
        self.root.geometry("920x640")
        self.root.minsize(780, 520)

        self.python_bin = self._resolve_python_bin()
        self.llm_enabled = tk.BooleanVar(value=True)
        self.model_name = tk.StringVar(value=os.getenv("NETWORK_AGENT_LOCAL_MODEL", "llama3.2"))
        self.status_text = tk.StringVar(value="Ready")
        self._is_busy = False

        self._build_layout()
        self._append_system(
            "Welcome. Enter a network issue (example: 'I cannot reach 8.8.8.8').\n"
            "The app can start a local LLM with Ollama if available."
        )

    def _resolve_python_bin(self) -> str:
        if os.name == "nt":
            venv_python = os.path.join(ROOT_DIR, ".venv", "Scripts", "python.exe")
            if os.path.exists(venv_python):
                return venv_python
            return "py"
        venv_python = os.path.join(ROOT_DIR, ".venv", "bin", "python")
        if os.path.exists(venv_python):
            return venv_python
        return "python3"

    def _llm_start_command(self, model: str) -> list[str]:
        if os.name == "nt":
            return ["cmd", "/c", os.path.join(ROOT_DIR, "llm", "spin_llm.bat"), model]
        return [os.path.join(ROOT_DIR, "llm", "spin_llm.sh"), model]

    def _runtime_env(self) -> dict[str, str]:
        env = os.environ.copy()
        src_path = os.path.join(ROOT_DIR, "src")
        existing = env.get("PYTHONPATH", "").strip()
        if existing:
            env["PYTHONPATH"] = f"{src_path}{os.pathsep}{existing}"
        else:
            env["PYTHONPATH"] = src_path
        return env

    def _build_layout(self) -> None:
        top = ttk.Frame(self.root, padding=12)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Model").pack(side=tk.LEFT)
        ttk.Entry(top, textvariable=self.model_name, width=20).pack(side=tk.LEFT, padx=(8, 12))
        ttk.Checkbutton(top, text="Use local LLM (Ollama)", variable=self.llm_enabled).pack(side=tk.LEFT)
        ttk.Button(top, text="Start LLM", command=self.start_llm).pack(side=tk.LEFT, padx=12)

        chat_frame = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        chat_frame.pack(fill=tk.BOTH, expand=True)

        self.chat_box = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, state=tk.DISABLED, font=("Menlo", 12))
        self.chat_box.pack(fill=tk.BOTH, expand=True)

        input_frame = ttk.Frame(self.root, padding=12)
        input_frame.pack(fill=tk.X)

        self.input_box = tk.Text(input_frame, height=3, wrap=tk.WORD, font=("Menlo", 12))
        self.input_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.input_box.bind("<Return>", self._on_enter_pressed)
        self.input_box.bind("<Shift-Return>", lambda e: None)

        send_btn = ttk.Button(input_frame, text="Send", command=self.send_message)
        send_btn.pack(side=tk.LEFT, padx=(12, 0))

        status = ttk.Label(self.root, textvariable=self.status_text, relief=tk.SUNKEN, anchor=tk.W, padding=(8, 4))
        status.pack(side=tk.BOTTOM, fill=tk.X)

    def _append_chat(self, speaker: str, message: str) -> None:
        self.chat_box.configure(state=tk.NORMAL)
        self.chat_box.insert(tk.END, f"{speaker}> {message}\n\n")
        self.chat_box.see(tk.END)
        self.chat_box.configure(state=tk.DISABLED)

    def _append_system(self, message: str) -> None:
        self._append_chat("System", message)

    def _append_user(self, message: str) -> None:
        self._append_chat("You", message)

    def _append_agent(self, message: str) -> None:
        self._append_chat("Agent", message)

    def _set_busy(self, busy: bool) -> None:
        self._is_busy = busy
        self.input_box.configure(state=tk.DISABLED if busy else tk.NORMAL)

    def _on_enter_pressed(self, event: tk.Event[Any]) -> str:
        if event.state & 0x0001:  # Shift key
            return ""
        self.send_message()
        return "break"

    def start_llm(self) -> None:
        if self._is_busy:
            return

        def _run() -> None:
            self.root.after(0, lambda: self.status_text.set("Starting local LLM..."))
            model = self.model_name.get().strip() or "llama3.2"
            env = os.environ.copy()
            env["NETWORK_AGENT_LOCAL_MODEL"] = model
            try:
                proc = subprocess.run(
                    self._llm_start_command(model),
                    cwd=ROOT_DIR,
                    env=env,
                    text=True,
                    capture_output=True,
                    check=False,
                )
            except FileNotFoundError:
                self.root.after(
                    0,
                    lambda: self._append_system("LLM startup script not found at ./llm/spin_llm.sh or ./llm/spin_llm.bat"),
                )
                self.root.after(0, lambda: self.status_text.set("LLM unavailable"))
                return

            if proc.returncode == 0:
                self.root.after(0, lambda: self._append_system(f"Local LLM started with model '{model}'."))
                self.root.after(0, lambda: self.status_text.set("LLM ready"))
            else:
                message = "Ollama not installed or model start failed. Program will run manually."
                self.root.after(0, lambda: self._append_system(message))
                self.root.after(0, lambda: self.status_text.set("LLM unavailable - manual mode"))

        threading.Thread(target=_run, daemon=True).start()

    def send_message(self) -> None:
        if self._is_busy:
            return
        prompt = self.input_box.get("1.0", tk.END).strip()
        if not prompt:
            return
        self.input_box.delete("1.0", tk.END)
        self._append_user(prompt)
        self._set_busy(True)
        self.status_text.set("Running diagnosis...")

        def _run() -> None:
            cmd = [
                self.python_bin,
                "-m",
                "network_agent.cli",
                "--prompt",
                prompt,
                "--host-os",
                "auto",
                "--collect-live-stats",
            ]
            if self.llm_enabled.get():
                model = self.model_name.get().strip() or "llama3.2"
                cmd.extend(
                    [
                        "--enable-llm-agents",
                        "--agent-llm-provider",
                        "ollama",
                        "--agent-llm-model",
                        model,
                        "--agent-llm-base-url",
                        "http://127.0.0.1:11434/api/chat",
                    ]
                )

            proc = subprocess.run(
                cmd,
                cwd=ROOT_DIR,
                env=self._runtime_env(),
                text=True,
                capture_output=True,
                check=False,
            )
            if proc.returncode != 0:
                err = proc.stderr.strip() or "Unknown error"
                self.root.after(0, lambda: self._append_agent(f"Execution failed: {err}"))
                self.root.after(0, lambda: self.status_text.set("Execution failed"))
                self.root.after(0, lambda: self._set_busy(False))
                return

            try:
                payload = json.loads(proc.stdout)
            except json.JSONDecodeError:
                self.root.after(0, lambda: self._append_agent("Received non-JSON output from network-agent."))
                self.root.after(0, lambda: self.status_text.set("Invalid output"))
                self.root.after(0, lambda: self._set_busy(False))
                return

            summary = self._format_agent_reply(payload)
            self.root.after(0, lambda: self._append_agent(summary))
            self.root.after(0, lambda: self.status_text.set("Ready"))
            self.root.after(0, lambda: self._set_busy(False))

        threading.Thread(target=_run, daemon=True).start()

    def _format_agent_reply(self, payload: dict[str, Any]) -> str:
        diagnosis = payload.get("diagnosis", {})
        validation = payload.get("validation", {})

        top_cause = "n/a"
        causes = diagnosis.get("candidate_causes_ranked", [])
        if causes and isinstance(causes, list) and isinstance(causes[0], dict):
            top_cause = str(causes[0].get("title", "n/a"))

        parts = [
            f"Summary: {diagnosis.get('problem_summary', 'n/a')}",
            f"Top cause: {top_cause}",
            f"Confidence: {diagnosis.get('confidence_score', 'n/a')}",
        ]

        remediation = diagnosis.get("remediation_plan", [])
        if isinstance(remediation, list) and remediation:
            parts.append("Remediation:")
            for step in remediation[:3]:
                parts.append(f"- {step}")

        notes = validation.get("reasons", [])
        if isinstance(notes, list) and notes:
            parts.append("Validation notes:")
            for reason in notes:
                parts.append(f"- {reason}")

        return "\n".join(parts)


def main() -> None:
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    app = NetworkAgentChatGUI(root)
    app.start_llm()
    root.mainloop()


if __name__ == "__main__":
    main()
