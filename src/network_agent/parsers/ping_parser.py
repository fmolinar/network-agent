from __future__ import annotations

import re
from typing import Any


_LOSS_RE = re.compile(r"(\d+(?:\.\d+)?)%\s*packet loss")
_RTT_RE = re.compile(r"=\s*([\d.]+)/([\d.]+)/([\d.]+)")


def parse_ping_output(raw: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    loss_match = _LOSS_RE.search(raw)
    if loss_match:
        out["packet_loss_pct"] = float(loss_match.group(1))

    rtt_match = _RTT_RE.search(raw)
    if rtt_match:
        out["rtt_min_ms"] = float(rtt_match.group(1))
        out["rtt_avg_ms"] = float(rtt_match.group(2))
        out["rtt_max_ms"] = float(rtt_match.group(3))
    return out
