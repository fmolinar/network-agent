from network_agent.agents.planner import Planner
from network_agent.core.host_os import HostOS
from network_agent.core.schemas import Category


def test_planner_classifies_dns() -> None:
    planner = Planner()
    category = planner.classify("my dns is broken", {"logs": "SERVFAIL resolving host"})
    assert category == Category.DNS


def test_planner_windows_uses_tracert() -> None:
    planner = Planner()
    plan = planner.plan("cannot reach internet", {"ping": "loss"}, host_os=HostOS.WINDOWS)
    assert "tracert" in plan.selected_checks


def test_planner_classifies_can_reach_phrase_as_connectivity() -> None:
    planner = Planner()
    category = planner.classify("test if I can reach 8.8.8.8", {})
    assert category == Category.CONNECTIVITY
