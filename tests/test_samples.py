from __future__ import annotations

import json
from pathlib import Path

from network_agent.engine import NetworkTroubleshootingEngine


SAMPLES_ROOT = Path("samples")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_sample_fixtures_produce_expected_diagnoses() -> None:
    scenarios = [
        "connectivity_loss",
        "dns_failure",
        "routing_timeout",
        "transport_retransmits",
        "security_tls_block",
    ]
    engine = NetworkTroubleshootingEngine(audit_path="/tmp/network-agent-samples-audit.log", host_os="linux")

    for scenario in scenarios:
        folder = SAMPLES_ROOT / scenario
        expected = json.loads(_read(folder / "expected.json"))
        result = engine.run(
            _read(folder / "prompt.txt").strip(),
            {
                "ping": _read(folder / "ping.txt"),
                "traceroute": _read(folder / "traceroute.txt"),
                "logs": _read(folder / "logs.txt"),
                "pcap_summary": _read(folder / "pcap_summary.txt"),
            },
        )

        assert result["plan"]["category"] == expected["category"]
        assert result["diagnosis"]["confidence_score"] >= expected["min_confidence"]
        top_cause = result["diagnosis"]["candidate_causes_ranked"][0]["title"]
        assert expected["expected_cause_contains"].lower() in top_cause.lower()
