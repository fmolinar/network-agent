#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from tkinter import scrolledtext
from tkinter import ttk
from typing import Any


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class NetworkAgentChatGUI:
    BG = "#f2f6fb"
    CARD_BG = "#ffffff"
    CARD_BORDER = "#d9e3ef"
    TITLE = "#10243f"
    SUBTITLE = "#5b6b81"
    SYSTEM_META = "#42556f"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Network Agent")
        self.root.geometry("980x700")
        self.root.minsize(840, 580)
        self.root.configure(bg=self.BG)

        self.python_bin = self._resolve_python_bin()
        self.llm_enabled = tk.BooleanVar(value=True)
        self.model_name = tk.StringVar(value=os.getenv("NETWORK_AGENT_LOCAL_MODEL", "llama3.2"))
        self.status_text = tk.StringVar(value="Ready")
        self.status_badge = tk.StringVar(value="READY")
        self._is_busy = False
        self._loading_count = 0
        self._logo_image: tk.PhotoImage | None = None
        self._command_tag_counter = 0
        self._command_tag_map: dict[str, str] = {}

        self._configure_styles()
        self._build_layout()
        self._append_system(
            "Welcome to Network Agent. Describe your network issue in the chat box below.\n"
            "The app attempts to start the local LLM automatically and will fall back to manual mode if unavailable."
        )

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure("App.TFrame", background=self.BG)
        style.configure("Card.TFrame", background=self.CARD_BG)
        style.configure("Title.TLabel", background=self.CARD_BG, foreground=self.TITLE, font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", background=self.CARD_BG, foreground=self.SUBTITLE, font=("Segoe UI", 10))
        style.configure("Label.TLabel", background=self.CARD_BG, foreground="#1f3b59", font=("Segoe UI", 10, "bold"))
        style.configure("Status.TLabel", background="#e8f2ff", foreground="#16487a", font=("Segoe UI", 9, "bold"), padding=(10, 4))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 8))
        style.configure(
            "Loader.Horizontal.TProgressbar",
            troughcolor="#eaf0f8",
            background="#2a7bd1",
            bordercolor="#eaf0f8",
            lightcolor="#2a7bd1",
            darkcolor="#2a7bd1",
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

    def _load_logo(self) -> tk.Label:
        logo_label = tk.Label(bg=self.CARD_BG)
        candidates = [
            os.path.join(ROOT_DIR, "images", "logo-network-agent.png"),
            os.path.join(ROOT_DIR, "logo-network-agent.png"),
            os.path.join(ROOT_DIR, "gui", "logo-network-agent.png"),
        ]
        for logo_path in candidates:
            if not os.path.exists(logo_path):
                continue
            try:
                img = tk.PhotoImage(file=logo_path)
                if img.width() > 68:
                    factor = max(1, img.width() // 68)
                    img = img.subsample(factor, factor)
                self._logo_image = img
                logo_label.configure(image=self._logo_image)
                return logo_label
            except Exception:  # noqa: BLE001
                continue

        logo_label.configure(text="NA", fg="#1a4f82", bg="#d9eaff", font=("Segoe UI", 13, "bold"), width=3, height=1)
        return logo_label

    def _build_layout(self) -> None:
        main = ttk.Frame(self.root, style="App.TFrame", padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(main, bg=self.CARD_BG, highlightbackground=self.CARD_BORDER, highlightthickness=1)
        header.pack(fill=tk.X, pady=(0, 12))

        header_top = ttk.Frame(header, style="Card.TFrame", padding=(14, 12, 14, 8))
        header_top.pack(fill=tk.X)

        logo = self._load_logo()
        logo.pack(side=tk.LEFT, padx=(0, 12))

        title_group = ttk.Frame(header_top, style="Card.TFrame")
        title_group.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(title_group, text="Network Agent", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_group, text="Offline troubleshooting with local LLM support", style="Subtitle.TLabel").pack(anchor="w", pady=(2, 0))

        status_group = ttk.Frame(header_top, style="Card.TFrame")
        status_group.pack(side=tk.RIGHT, anchor="e")
        ttk.Label(status_group, textvariable=self.status_badge, style="Status.TLabel").pack(side=tk.TOP, anchor="e")
        self.loading_row = ttk.Frame(status_group, style="Card.TFrame")
        self.loading_label = ttk.Label(self.loading_row, text="Working...", style="Subtitle.TLabel")
        self.loading_label.pack(side=tk.LEFT, padx=(0, 8))
        self.loading_bar = ttk.Progressbar(
            self.loading_row,
            mode="indeterminate",
            length=120,
            style="Loader.Horizontal.TProgressbar",
        )
        self.loading_bar.pack(side=tk.LEFT)

        controls = ttk.Frame(header, style="Card.TFrame", padding=(14, 0, 14, 14))
        controls.pack(fill=tk.X)

        ttk.Label(controls, text="Model", style="Label.TLabel").grid(row=0, column=0, sticky="w")
        model_entry = ttk.Entry(controls, textvariable=self.model_name, width=18)
        model_entry.grid(row=0, column=1, sticky="w", padx=(8, 12))

        ttk.Checkbutton(controls, text="Use local LLM", variable=self.llm_enabled).grid(row=0, column=2, sticky="w")
        ttk.Button(controls, text="Start LLM", style="Primary.TButton", command=self.start_llm).grid(row=0, column=3, padx=(12, 0), sticky="e")
        controls.columnconfigure(4, weight=1)

        chat_card = tk.Frame(main, bg=self.CARD_BG, highlightbackground=self.CARD_BORDER, highlightthickness=1)
        chat_card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        self.chat_box = scrolledtext.ScrolledText(
            chat_card,
            wrap=tk.WORD,
            state=tk.NORMAL,
            font=("Segoe UI", 11),
            bg="#fbfdff",
            fg="#17324f",
            relief=tk.FLAT,
            borderwidth=0,
            padx=12,
            pady=12,
            insertbackground="#17324f",
        )
        self.chat_box.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._configure_chat_tags()
        self.chat_box.bind("<Key>", self._block_chat_edit)
        self.chat_box.bind("<<Paste>>", lambda _: "break")

        input_card = tk.Frame(main, bg=self.CARD_BG, highlightbackground=self.CARD_BORDER, highlightthickness=1)
        input_card.pack(fill=tk.X)

        input_frame = ttk.Frame(input_card, style="Card.TFrame", padding=12)
        input_frame.pack(fill=tk.X)

        self.input_box = tk.Text(
            input_frame,
            height=3,
            wrap=tk.WORD,
            font=("Segoe UI", 11),
            bg="#ffffff",
            fg="#17324f",
            relief=tk.FLAT,
            borderwidth=0,
            insertbackground="#17324f",
            padx=6,
            pady=6,
        )
        self.input_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.input_box.bind("<Return>", self._on_enter_pressed)
        self.input_box.bind("<Shift-Return>", lambda e: None)

        ttk.Button(input_frame, text="Send", style="Primary.TButton", command=self.send_message).pack(side=tk.LEFT, padx=(12, 0))

        status_line = tk.Label(
            self.root,
            textvariable=self.status_text,
            bg="#e9f0f8",
            fg="#27415f",
            font=("Segoe UI", 9),
            anchor="w",
            padx=10,
            pady=6,
        )
        status_line.pack(side=tk.BOTTOM, fill=tk.X)

    def _configure_chat_tags(self) -> None:
        self.chat_box.tag_configure("meta_system", foreground="#4d6786", font=("Segoe UI", 9, "bold"), spacing1=6)
        self.chat_box.tag_configure("meta_user", foreground="#3a5f8f", font=("Segoe UI", 9, "bold"), justify="right", rmargin=16)
        self.chat_box.tag_configure("meta_agent", foreground="#2d5b46", font=("Segoe UI", 9, "bold"))

        self.chat_box.tag_configure(
            "bubble_system",
            background="#eef3f8",
            foreground="#1f3b59",
            lmargin1=14,
            lmargin2=14,
            rmargin=220,
            spacing3=10,
        )
        self.chat_box.tag_configure(
            "bubble_user",
            background="#e3efff",
            foreground="#1b3e66",
            justify="right",
            lmargin1=220,
            lmargin2=220,
            rmargin=14,
            spacing3=10,
        )
        self.chat_box.tag_configure(
            "bubble_agent",
            background="#e7f6ef",
            foreground="#1e4d3a",
            lmargin1=14,
            lmargin2=14,
            rmargin=220,
            spacing3=10,
        )
        self.chat_box.tag_configure(
            "bubble_command",
            background="#d9f0e2",
            foreground="#0c5d35",
            lmargin1=20,
            lmargin2=20,
            rmargin=230,
            underline=True,
            spacing3=6,
        )

    def _set_status(self, text: str, badge: str | None = None) -> None:
        self.status_text.set(text)
        if badge is not None:
            self.status_badge.set(badge)

    def _loading_start(self) -> None:
        self._loading_count += 1
        if self._loading_count == 1:
            self.loading_row.pack(side=tk.TOP, anchor="e", pady=(6, 0))
            self.loading_bar.start(11)

    def _loading_stop(self) -> None:
        if self._loading_count <= 0:
            return
        self._loading_count -= 1
        if self._loading_count == 0:
            self.loading_bar.stop()
            self.loading_row.pack_forget()

    def _append_chat(self, speaker: str, message: str) -> None:
        speaker_key = speaker.lower()
        meta_tag = {
            "system": "meta_system",
            "you": "meta_user",
            "agent": "meta_agent",
        }.get(speaker_key, "meta_system")
        bubble_tag = {
            "system": "bubble_system",
            "you": "bubble_user",
            "agent": "bubble_agent",
        }.get(speaker_key, "bubble_system")

        timestamp = datetime.now().strftime("%H:%M")
        self.chat_box.insert(tk.END, f"{speaker}  {timestamp}\n", meta_tag)
        for line in (message.strip() or " ").splitlines():
            self.chat_box.insert(tk.END, f"{line}\n", bubble_tag)
        self.chat_box.insert(tk.END, "\n")
        self.chat_box.see(tk.END)

    def _append_agent(self, message: str, commands: list[str] | None = None) -> None:
        self._append_chat("Agent", message)
        if not commands:
            return
        self.chat_box.insert(tk.END, "Click to paste command:\n", "meta_agent")
        for command in commands:
            cmd = command.strip()
            if not cmd:
                continue
            self._command_tag_counter += 1
            tag = f"cmd_tag_{self._command_tag_counter}"
            self._command_tag_map[tag] = cmd
            self.chat_box.insert(tk.END, f"{cmd}\n", ("bubble_command", tag))
            self.chat_box.tag_bind(tag, "<Button-1>", self._on_command_click)
            self.chat_box.tag_bind(tag, "<Enter>", lambda _: self.chat_box.config(cursor="hand2"))
            self.chat_box.tag_bind(tag, "<Leave>", lambda _: self.chat_box.config(cursor="xterm"))
        self.chat_box.insert(tk.END, "\n")
        self.chat_box.see(tk.END)

    def _append_system(self, message: str) -> None:
        self._append_chat("System", message)

    def _append_user(self, message: str) -> None:
        self._append_chat("You", message)

    def _on_command_click(self, event: tk.Event[Any]) -> None:
        tags = self.chat_box.tag_names(f"@{event.x},{event.y}")
        command = None
        for tag in tags:
            if tag.startswith("cmd_tag_"):
                command = self._command_tag_map.get(tag)
                break
        if not command:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(command)
        self.input_box.configure(state=tk.NORMAL)
        self.input_box.delete("1.0", tk.END)
        self.input_box.insert("1.0", command)
        self._set_status("Command pasted to input and copied to clipboard", "READY")

    def _block_chat_edit(self, event: tk.Event[Any]) -> str | None:
        ctrl_or_cmd = bool(event.state & 0x4) or bool(event.state & 0x8)
        if ctrl_or_cmd and event.keysym.lower() in {"c", "a"}:
            return None
        if event.keysym in {"Left", "Right", "Up", "Down", "Prior", "Next", "Home", "End"}:
            return None
        return "break"

    def _set_busy(self, busy: bool) -> None:
        self._is_busy = busy
        self.input_box.configure(state=tk.DISABLED if busy else tk.NORMAL)
        if busy:
            self._loading_start()
        else:
            self._loading_stop()

    def _on_enter_pressed(self, event: tk.Event[Any]) -> str:
        if event.state & 0x0001:
            return ""
        self.send_message()
        return "break"

    def start_llm(self) -> None:
        if self._is_busy:
            return

        def _run() -> None:
            self.root.after(0, self._loading_start)
            self.root.after(0, lambda: self._set_status("Starting local LLM...", "STARTING LLM"))
            model = self.model_name.get().strip() or "llama3.2"
            env = os.environ.copy()
            env["NETWORK_AGENT_LOCAL_MODEL"] = model
            try:
                proc = subprocess.run(
                    self._llm_start_command(model),
                    cwd=ROOT_DIR,
                    env=env,
                    text=True,
                    errors="replace",
                    capture_output=True,
                    check=False,
                )
            except FileNotFoundError:
                self.root.after(
                    0,
                    lambda: self._append_system("LLM startup script not found at ./llm/spin_llm.sh or ./llm/spin_llm.bat"),
                )
                self.root.after(0, lambda: self._set_status("LLM unavailable", "MANUAL MODE"))
                self.root.after(0, self._loading_stop)
                return

            if proc.returncode == 0:
                self.root.after(0, lambda: self._append_system(f"Local LLM started with model '{model}'."))
                self.root.after(0, lambda: self._set_status("LLM ready", "LLM READY"))
            else:
                self.root.after(0, lambda: self._append_system("Ollama not installed or model start failed. Running manual mode."))
                self.root.after(0, lambda: self._set_status("LLM unavailable - manual mode", "MANUAL MODE"))
            self.root.after(0, self._loading_stop)

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
        self._set_status("Running diagnosis...", "WORKING")

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
                "--execute-proposed-commands",
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
                errors="replace",
                capture_output=True,
                check=False,
            )
            if proc.returncode != 0:
                err = proc.stderr.strip() or "Unknown error"
                self.root.after(0, lambda: self._append_agent(f"Execution failed: {err}"))
                self.root.after(0, lambda: self._set_status("Execution failed", "ERROR"))
                self.root.after(0, lambda: self._set_busy(False))
                return

            try:
                payload = json.loads(proc.stdout)
            except json.JSONDecodeError:
                self.root.after(0, lambda: self._append_agent("Received non-JSON output from network-agent."))
                self.root.after(0, lambda: self._set_status("Invalid output", "ERROR"))
                self.root.after(0, lambda: self._set_busy(False))
                return

            summary, command_suggestions = self._format_agent_reply(payload)
            self.root.after(0, lambda: self._append_agent(summary, command_suggestions))
            self.root.after(0, lambda: self._set_status("Ready", "READY"))
            self.root.after(0, lambda: self._set_busy(False))

        threading.Thread(target=_run, daemon=True).start()

    def _format_agent_reply(self, payload: dict[str, Any]) -> tuple[str, list[str]]:
        diagnosis = payload.get("diagnosis", {})
        validation = payload.get("validation", {})
        metadata = diagnosis.get("metadata", {}) if isinstance(diagnosis, dict) else {}

        top_cause = "n/a"
        causes = diagnosis.get("candidate_causes_ranked", [])
        if causes and isinstance(causes, list) and isinstance(causes[0], dict):
            top_cause = str(causes[0].get("title", "n/a"))

        lines = [
            f"Summary: {diagnosis.get('problem_summary', 'n/a')}",
            f"Top cause: {top_cause}",
            f"Confidence: {diagnosis.get('confidence_score', 'n/a')}",
        ]
        user_explanation = metadata.get("user_explanation")
        if isinstance(user_explanation, str) and user_explanation.strip():
            lines.append(f"Plain explanation: {user_explanation.strip()}")

        commands_ran = metadata.get("commands_ran", [])
        if isinstance(commands_ran, list) and commands_ran:
            lines.append(f"Commands run: {', '.join(str(c) for c in commands_ran[:6])}")
        logic = metadata.get("command_logic")
        if isinstance(logic, str) and logic.strip():
            lines.append(f"Logic: {logic.strip()}")

        remediation = diagnosis.get("remediation_plan", [])
        if isinstance(remediation, list) and remediation:
            lines.append("Remediation:")
            lines.extend(f"- {step}" for step in remediation[:3])

        notes = validation.get("reasons", [])
        if isinstance(notes, list) and notes:
            lines.append("Validation notes:")
            lines.extend(f"- {reason}" for reason in notes)

        command_suggestions_raw = metadata.get("proposed_commands", [])
        command_suggestions = [str(c).strip() for c in command_suggestions_raw] if isinstance(command_suggestions_raw, list) else []
        command_suggestions = [c for c in command_suggestions if c]
        return "\n".join(lines), command_suggestions


def main() -> None:
    root = tk.Tk()
    app = NetworkAgentChatGUI(root)
    app.start_llm()
    root.mainloop()


if __name__ == "__main__":
    main()
