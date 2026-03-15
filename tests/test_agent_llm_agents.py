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
