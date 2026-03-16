from __future__ import annotations

from network_agent.core.agent_llm import AgentLLMConfig
from network_agent.engine import NetworkTroubleshootingEngine


def test_engine_supports_llm_assisted_agents_with_mock_provider() -> None:
    engine = NetworkTroubleshootingEngine(
        audit_path="/tmp/network-agent-test-audit.log",
        host_os="linux",
        agent_llm_config=AgentLLMConfig(provider="mock", model="mock-local"),
    )
    result = engine.run(
        "I cannot reach 8.8.8.8",
        {
            "ping": "5 packets transmitted, 3 received, 40% packet loss",
            "traceroute": "1 192.168.1.1 1.0 ms\n2 10.0.0.1 20.0 ms",
            "logs": "intermittent network issue",
        },
    )
    assert result["plan"]["rationale"] == "mock llm planner response"
    assert result["diagnosis"]["metadata"]["generation_mode"] == "llm"
    assert result["diagnosis"]["candidate_causes_ranked"]


def test_engine_can_export_agent_prompts() -> None:
    engine = NetworkTroubleshootingEngine(
        audit_path="/tmp/network-agent-test-audit.log",
        host_os="linux",
    )
    result = engine.run(
        "I cannot reach 8.8.8.8",
        {
            "ping": "5 packets transmitted, 5 received, 0% packet loss",
            "traceroute": "1 192.168.1.1 1.0 ms",
            "logs": "normal operation",
        },
        capture_agent_prompts=True,
    )
    assert "agent_prompts" in result
    assert set(result["agent_prompts"].keys()) == {"planner", "generator", "validator"}


class _DictCommandConnector:
    def ask_json(self, system_prompt: str, user_prompt: str, task: str) -> dict:
        if task == "planner":
            return {
                "category": "connectivity",
                "selected_checks": ["ping", "traceroute", "logs"],
                "rationale": "dict command planner",
            }
        if task == "generator":
            return {
                "problem_summary": "LLM diagnosis with dict command objects.",
                "candidate_causes_ranked": [
                    {
                        "title": "Path instability",
                        "confidence": 0.75,
                        "required_evidence": ["traceroute"],
                        "remediation_steps": ["Check path quality"],
                    }
                ],
                "confidence_score": 0.75,
                "required_evidence": ["traceroute"],
                "remediation_plan": ["Check path quality"],
                "proposed_commands": [{"command": "ping 8.8.8.8"}, {"command": "traceroute 8.8.8.8"}],
                "command_logic": "Run active checks to confirm hop behavior before summarizing.",
            }
        return {}


class _FakeRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def run(self, command: str, user_approved: bool = False, timeout_seconds: int | None = None) -> str:
        self.calls.append(command)
        if command.startswith("ping "):
            return "5 packets transmitted, 5 received, 0% packet loss"
        if command.startswith("traceroute "):
            return "1 192.168.1.1 1.0 ms\n2 10.0.0.1 2.0 ms"
        return "ok"


def test_engine_executes_llm_proposed_commands_before_final_summary() -> None:
    engine = NetworkTroubleshootingEngine(
        audit_path="/tmp/network-agent-test-audit.log",
        host_os="linux",
        agent_llm_config=AgentLLMConfig(provider="none"),
    )
    connector = _DictCommandConnector()
    engine.planner.llm_connector = connector
    engine.generator.llm_connector = connector
    fake_runner = _FakeRunner()
    engine.executor.runner = fake_runner  # type: ignore[assignment]

    result = engine.run(
        "Diagnose unstable connectivity",
        {
            "ping": "5 packets transmitted, 4 received, 20% packet loss",
            "traceroute": "1 192.168.1.1 1.0 ms\n2 10.0.0.1 2.0 ms",
            "logs": "intermittent jitter",
        },
        collect_live_stats=True,
    )

    metadata = result["diagnosis"]["metadata"]
    assert metadata["commands_ran"]
    assert "ping 8.8.8.8" in metadata["commands_ran"]
    assert "command_logic" in metadata
    assert fake_runner.calls
    assert not any("{'command':" in reason for reason in result["validation"]["reasons"])
