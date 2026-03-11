from __future__ import annotations

from typing import Any


def parse_pcap_summary(raw: str) -> dict[str, Any]:
    # Accepts simple key=value lines: retransmits=12\nresets=3\ndns_failures=4
    parsed: dict[str, Any] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.isdigit():
            parsed[key] = int(value)
        else:
            try:
                parsed[key] = float(value)
            except ValueError:
                parsed[key] = value
    return parsed
