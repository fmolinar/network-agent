from __future__ import annotations

from dataclasses import dataclass, field

from network_agent.agents.executor import Executor
from network_agent.core.host_os import HostOS
from network_agent.core.schemas import Category, PlannerPlan


@dataclass
class FakeRunner:
    calls: list[str] = field(default_factory=list)
    timeouts: list[int | None] = field(default_factory=list)

    def run(self, command: str, user_approved: bool = False, timeout_seconds: int | None = None) -> str:
        self.calls.append(command)
        self.timeouts.append(timeout_seconds)
        if command.startswith("ping"):
            return "4 packets transmitted, 4 received, 0% packet loss\nrtt min/avg/max/mdev = 9.0/10.0/11.0/1.0 ms"
        if command.startswith("traceroute"):
            return "1 192.168.1.1 1.0 ms\n2 10.0.0.1 2.0 ms"
        if command.startswith("route print"):
            return "0.0.0.0          0.0.0.0      10.0.0.1"
        if command.startswith("arp"):
            return "? (10.0.0.1) at aa:bb:cc:dd:ee:ff on en0"
        if command.startswith("ip -br addr"):
            return "eth0 UP 10.0.0.5/24"
        if command.startswith("netstat"):
            return "Kernel IP routing table\ndefault via 10.0.0.1 dev eth0"
        if command.startswith("tcpdump"):
            return "Packets: 120, retransmits: 7, drops: 1"
        return ""


def test_executor_collects_live_stats_when_enabled() -> None:
    plan = PlannerPlan(
        category=Category.CONNECTIVITY,
        selected_checks=["ping", "traceroute", "netstat"],
        rationale="test",
        host_os=HostOS.LINUX,
    )
    runner = FakeRunner()
    executor = Executor(runner=runner)
    result = executor.run(
        plan,
        artifacts={},
        user_prompt="cannot reach 1.1.1.1",
        collect_live_stats=True,
    )

    assert "ping" in result.executed_checks
    assert "traceroute" in result.executed_checks
    assert "netstat" in result.executed_checks
    assert not result.missing_checks
    assert {"ping", "traceroute", "netstat"}.issubset(set(result.collection_attempts.keys()))
    assert not result.collection_errors
    assert runner.calls
    assert result.network_topology["default_gateway"] == "10.0.0.1"
    assert result.network_topology["hop_count"] >= 1


def test_executor_builds_topology_from_artifacts() -> None:
    plan = PlannerPlan(
        category=Category.ROUTING,
        selected_checks=["traceroute", "routing_table"],
        rationale="test",
        host_os=HostOS.LINUX,
    )
    executor = Executor(runner=None)
    result = executor.run(
        plan,
        artifacts={
            "traceroute": "1 192.168.1.1 1.0 ms\n2 10.0.0.1 2.0 ms",
            "routing_table": "default via 192.168.1.1 dev eth0\n10.0.0.0/24 dev eth0 scope link",
            "arp_table": "? (192.168.1.1) at aa:bb:cc:dd:ee:ff on eth0",
            "interface_info": "eth0 UP 10.0.0.20/24",
        },
    )
    topo = result.network_topology
    assert topo["default_gateway"] == "192.168.1.1"
    assert topo["hop_count"] == 2
    assert topo["neighbor_count"] >= 1


def test_executor_windows_ping_uses_bounded_timeout() -> None:
    plan = PlannerPlan(
        category=Category.CONNECTIVITY,
        selected_checks=["ping"],
        rationale="test",
        host_os=HostOS.WINDOWS,
    )
    runner = FakeRunner()
    executor = Executor(runner=runner)
    result = executor.run(
        plan,
        artifacts={},
        user_prompt="cannot reach 8.8.8.8",
        collect_live_stats=True,
    )

    assert "ping" in result.executed_checks
    assert any(call.startswith("ping -n 4 -w 1000 ") for call in runner.calls)


def test_executor_live_capture_respects_capture_seconds() -> None:
    plan = PlannerPlan(
        category=Category.TRANSPORT,
        selected_checks=["pcap_summary"],
        rationale="test",
        host_os=HostOS.LINUX,
    )
    runner = FakeRunner()
    executor = Executor(runner=runner)
    result = executor.run(
        plan,
        artifacts={},
        user_prompt="please run a packet capture for 45 seconds",
        collect_live_stats=True,
        capture_seconds=30,
    )

    assert "pcap_summary" in result.executed_checks
    assert runner.calls[0] == "tcpdump -nn"
    assert runner.timeouts[0] == 48
