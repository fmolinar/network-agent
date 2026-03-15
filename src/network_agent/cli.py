from __future__ import annotations

import argparse
import json
from pathlib import Path

from network_agent.core.agent_llm import AgentLLMConfig
from network_agent.core.llm import LLMConfig
from network_agent.engine import NetworkTroubleshootingEngine


def _read_text(path: str | None) -> str:
    if not path:
        return ""
    return Path(path).read_text(encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Network agent troubleshooting runner")
    parser.add_argument("--prompt", required=True, help="User problem statement")
    parser.add_argument("--host-os", default="auto", choices=["auto", "macos", "linux", "windows"], help="Target host OS")
    parser.add_argument(
        "--collect-live-stats",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Attempt to run safe read-only diagnostics for missing artifacts (default: enabled)",
    )
    parser.add_argument(
        "--allow-config-changes",
        action="store_true",
        help="Allow configuration-changing commands only when explicitly approved",
    )
    parser.add_argument(
        "--capture-seconds",
        type=int,
        default=30,
        help="Duration for live packet capture checks (default: 30)",
    )
    parser.add_argument(
        "--skip-topology",
        action="store_true",
        help="Disable network topology snapshot generation",
    )
    parser.add_argument(
        "--enable-llm-critic",
        action="store_true",
        help="Enable optional LLM critic for ambiguous diagnoses",
    )
    parser.add_argument(
        "--enable-llm-agents",
        action="store_true",
        help="Enable LLM-assisted planner and generator agents",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Include per-agent request debug trace in output",
    )
    parser.add_argument(
        "--debug-output",
        help="Optional path to save request debug trace JSON",
    )
    parser.add_argument(
        "--llm-provider",
        choices=["mock", "openai", "anthropic", "ollama"],
        help="LLM provider for critic",
    )
    parser.add_argument("--llm-model", help="LLM model name for critic")
    parser.add_argument("--llm-base-url", help="LLM endpoint base URL override")
    parser.add_argument("--llm-api-key", help="LLM API key override")
    parser.add_argument(
        "--agent-llm-provider",
        choices=["none", "mock", "ollama", "openai", "openai_compatible"],
        help="LLM provider for planner/generator",
    )
    parser.add_argument("--agent-llm-model", help="LLM model name for planner/generator")
    parser.add_argument("--agent-llm-base-url", help="LLM endpoint base URL override for planner/generator")
    parser.add_argument("--agent-llm-api-key", help="LLM API key override for planner/generator")
    parser.add_argument("--dump-agent-prompts", help="Optional path to save planner/generator/validator prompts JSON")
    parser.add_argument("--ping")
    parser.add_argument("--traceroute")
    parser.add_argument("--logs")
    parser.add_argument("--pcap-summary")
    parser.add_argument("--audit-path", default="artifacts/audit.log")
    args = parser.parse_args()

    artifacts = {
        "ping": _read_text(args.ping),
        "traceroute": _read_text(args.traceroute),
        "logs": _read_text(args.logs),
        "pcap_summary": _read_text(args.pcap_summary),
    }
    artifacts = {k: v for k, v in artifacts.items() if v}

    llm_cfg = LLMConfig.from_env()
    if args.llm_provider:
        llm_cfg.provider = args.llm_provider
    if args.llm_model:
        llm_cfg.model = args.llm_model
    if args.llm_base_url:
        llm_cfg.base_url = args.llm_base_url
    if args.llm_api_key:
        llm_cfg.api_key = args.llm_api_key

    agent_llm_cfg = AgentLLMConfig.from_env()
    if args.agent_llm_provider:
        agent_llm_cfg.provider = args.agent_llm_provider
    if args.agent_llm_model:
        agent_llm_cfg.model = args.agent_llm_model
    if args.agent_llm_base_url:
        agent_llm_cfg.base_url = args.agent_llm_base_url
    if args.agent_llm_api_key:
        agent_llm_cfg.api_key = args.agent_llm_api_key
    if args.enable_llm_agents and agent_llm_cfg.provider in {"", "none"}:
        agent_llm_cfg.provider = "ollama"

    engine = NetworkTroubleshootingEngine(
        audit_path=args.audit_path,
        host_os=args.host_os,
        llm_config=llm_cfg,
        agent_llm_config=agent_llm_cfg,
    )
    debug_enabled = args.debug or bool(args.debug_output)
    result = engine.run(
        args.prompt,
        artifacts,
        collect_live_stats=args.collect_live_stats,
        allow_config_changes=args.allow_config_changes,
        capture_seconds=max(5, min(args.capture_seconds, 300)),
        include_topology=not args.skip_topology,
        use_llm_critic=args.enable_llm_critic,
        capture_agent_prompts=bool(args.dump_agent_prompts),
        debug=debug_enabled,
    )

    if args.debug_output and "debug" in result:
        debug_path = Path(args.debug_output)
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(json.dumps(result["debug"], indent=2), encoding="utf-8")

    if args.dump_agent_prompts and "agent_prompts" in result:
        prompts_path = Path(args.dump_agent_prompts)
        prompts_path.parent.mkdir(parents=True, exist_ok=True)
        prompts_path.write_text(json.dumps(result["agent_prompts"], indent=2), encoding="utf-8")

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
