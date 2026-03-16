# Network Agent GUI

This folder contains a desktop GUI for `network-agent` with a chat-window experience.

## Files
- `chat_app.py`: Tkinter chat application
- `run_gui.sh`: launcher script
- `run_gui.bat`: Windows launcher script
- `../images/logo-network-agent.png`: logo shown in the app header

## What It Does
- Starts local LLM first (via `../llm/spin_llm.sh`) if available
- Falls back to manual mode if Ollama/model startup is unavailable
- Uses a modern card-based chat layout with status badge and message bubbles
- Renders the Network Agent logo in the header (`images/logo-network-agent.png`)
- Provides chat-like input/output:
  - you type a network issue
  - it runs `network_agent.cli`
  - it displays summary, top cause, confidence, and remediation

## Prerequisites
1. Python 3.10+
2. Project dependencies installed:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```
3. Optional local LLM runtime (offline mode): Ollama
   - Install: `https://ollama.com/download`

## Run
From repo root (macOS/Linux):
```bash
./gui/run_gui.sh
```

From repo root (Windows CMD):
```bat
gui\run_gui.bat
```

The launchers set `PYTHONPATH=src` automatically, so GUI/chat works even without editable install.

Direct run:
```bash
python gui/chat_app.py
```

Windows chat CLI wrapper:
```bat
llm\run_network_agent_chat.bat
```

## LLM Behavior
- On startup, the GUI attempts to run:
```bash
./llm/spin_llm.sh llama3.2
```
- On Windows, it attempts:
```bat
llm\spin_llm.bat llama3.2
```
- If that succeeds, LLM-assisted agents are enabled automatically.
- If that fails, it prints a system message and continues in manual mode.

## Controls
- `Model`: local model name (default `llama3.2`)
- `Use local LLM (Ollama)`: toggle for LLM-assisted planner/generator
- `Start LLM`: retry local LLM startup manually
- `Send`: run diagnosis for the current message
- `Enter`: send message
- `Shift+Enter`: newline in input box
- `Working...` loader: visible whenever a background task is running
- Agent command suggestions are clickable: click to copy + paste into the input box
- Chat transcript text is selectable for copy/paste

Tip: you can request capture duration directly in chat, for example:
- `run a packet capture for 60 seconds and diagnose retransmits`
