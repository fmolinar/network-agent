from network_agent.engine import NetworkTroubleshootingEngine


def test_engine_connectivity_case() -> None:
    engine = NetworkTroubleshootingEngine(audit_path="/tmp/network-agent-test-audit.log", host_os="linux")
    result = engine.run(
        "I can't reach 8.8.8.8",
        {
            "ping": "5 packets transmitted, 5 received, 0% packet loss\nrtt min/avg/max/mdev = 10.0/12.0/15.0/1.0 ms",
            "traceroute": "1 192.168.1.1 1.0 ms\n2 10.0.0.1 2.0 ms",
            "logs": "normal operation",
        },
    )

    assert result["plan"]["category"] in {"connectivity", "routing"}
    assert result["plan"]["host_os"] == "linux"
    assert result["diagnosis"]["candidate_causes_ranked"]
    assert "network_topology" in result["execution"]
    assert "hop_count" in result["execution"]["network_topology"]
    assert "validation" in result


def test_engine_debug_mode_exposes_agent_trace() -> None:
    engine = NetworkTroubleshootingEngine(audit_path="/tmp/network-agent-test-audit.log", host_os="linux")
    result = engine.run(
        "I can't reach 8.8.8.8",
        {
            "ping": "5 packets transmitted, 4 received, 20% packet loss\nrtt min/avg/max/mdev = 10.0/12.0/20.0/2.0 ms",
            "traceroute": "1 192.168.1.1 1.0 ms\n2 10.0.0.1 2.0 ms",
            "logs": "normal operation",
        },
        debug=True,
    )

    assert "debug" in result
    debug = result["debug"]
    assert debug["request_id"]
    assert debug["duration_ms"] >= 0
    ops = debug["agent_operations"]
    assert len(ops) == 4
    assert [op["agent"] for op in ops] == ["planner", "executor", "generator", "validator"]
