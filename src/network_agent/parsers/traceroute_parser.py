from __future__ import annotations

from typing import Any


def parse_traceroute_output(raw: str) -> dict[str, Any]:
    hops = 0
    timeout_hops = 0
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.split()[0].isdigit():
            hops += 1
            if "* * *" in stripped:
                timeout_hops += 1

    return {
        "hop_count": hops,
        "timeout_hops": timeout_hops,
        "timeout_ratio": (timeout_hops / hops) if hops else 0.0,
    }
