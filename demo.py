#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from network_agent.core.llm import LLMConfig
from network_agent.engine import NetworkTroubleshootingEngine


SCENARIOS = [
    "dns_failure",
    "connectivity_loss",
    "transport_retransmits",
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _scenario_artifacts(base: Path) -> dict[str, str]:
    return {
        "ping": _read(base / "ping.txt"),
        "traceroute": _read(base / "traceroute.txt"),
        "logs": _read(base / "logs.txt"),
        "pcap_summary": _read(base / "pcap_summary.txt"),
    }


def _top_cause(result: dict) -> str:
    causes = result.get("diagnosis", {}).get("candidate_causes_ranked", [])
    if not causes:
        return "n/a"
    return str(causes[0].get("title", "n/a"))


def _category_value(category: object) -> str:
    text = str(category)
    if text.startswith("Category."):
        return text.split(".", 1)[1].lower()
    return text


def run_demo(output_dir: Path, write_artifacts: bool) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Network Agent End-to-End Demo")
    print("Scenarios:", ", ".join(SCENARIOS))
    print()

    for scenario in SCENARIOS:
        scenario_dir = ROOT_DIR / "samples" / scenario
        prompt = _read(scenario_dir / "prompt.txt").strip()
        artifacts = _scenario_artifacts(scenario_dir)

        engine = NetworkTroubleshootingEngine(
            audit_path=str(output_dir / f"audit-{scenario}.log"),
            host_os="linux",
            llm_config=LLMConfig(provider="mock", model="mock-critic"),
        )
        result = engine.run(
            prompt,
            artifacts,
            collect_live_stats=False,
            use_llm_critic=True,
            debug=True,
        )

        summary = result["diagnosis"]["problem_summary"]
        top_cause = _top_cause(result)
        confidence = result["diagnosis"].get("confidence_score", "n/a")
        plan_category = _category_value(result["plan"].get("category", "n/a"))
        validator_reasons = result["validation"].get("reasons", [])
        op_trace = result.get("debug", {}).get("agent_operations", [])

        print(f"Scenario: {scenario}")
        print(f"  Prompt: {prompt}")
        print(f"  Category: {plan_category}")
        print(f"  Top cause: {top_cause}")
        print(f"  Confidence: {confidence}")
        print(f"  Agent operations: {len(op_trace)} (planner -> executor -> generator -> validator)")
        if validator_reasons:
            print("  Validation notes:")
            for reason in validator_reasons:
                print(f"    - {reason}")
        else:
            print("  Validation notes: none")
        print()

        if write_artifacts:
            out_path = output_dir / f"{scenario}.json"
            out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    if write_artifacts:
        print(f"Saved JSON outputs to: {output_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run 3 end-to-end network-agent scenarios")
    parser.add_argument(
        "--output-dir",
        default="examples/interactions",
        help="Directory where scenario JSON outputs are written",
    )
    parser.add_argument(
        "--no-write-artifacts",
        action="store_true",
        help="Do not write JSON outputs",
    )
    args = parser.parse_args()

    return run_demo(Path(args.output_dir), write_artifacts=not args.no_write_artifacts)


if __name__ == "__main__":
    raise SystemExit(main())
