# network_agent Package

Top-level package entrypoint:
- `NetworkTroubleshootingEngine`
- CLI command: `network-agent`

## Modules
- `engine.py`: Orchestrates planner -> executor -> generator -> validator with optional live stat collection
- `cli.py`: CLI runner with host/liveness/topology flags, optional LLM critic settings, and request debug mode
- `agents/`: Agent implementations
- `core/`: Shared schemas, OS profile detection, safety/audit primitives, and LLM provider client
- `parsers/`: Parsing logic for network artifacts and topology snapshots
- `tools/`: Whitelisted shell runner with approval-aware safety checks
