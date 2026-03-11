from __future__ import annotations

import re
from typing import Any

from network_agent.core.host_os import HostOS


_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_CIDR_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}/\d{1,2}\b")


def _extract_ips(text: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for ip in _IP_RE.findall(text):
        if ip not in seen:
            seen.add(ip)
            ordered.append(ip)
    return ordered


def parse_topology_snapshot(raw: dict[str, str], host_os: HostOS) -> dict[str, Any]:
    traceroute = raw.get("traceroute", "")
    routing = raw.get("routing_table", "") or raw.get("netstat", "")
    arp_table = raw.get("arp_table", "")
    interface_info = raw.get("interface_info", "")

    hops: list[str] = []
    for line in traceroute.splitlines():
        ips = _extract_ips(line)
        if ips:
            hops.append(ips[0])

    routes = _CIDR_RE.findall(routing)
    routing_ips = _extract_ips(routing)

    default_gateway = None
    routing_low = routing.lower()
    if host_os == HostOS.WINDOWS:
        for line in routing.splitlines():
            if line.strip().startswith("0.0.0.0"):
                ips = _extract_ips(line)
                if len(ips) >= 2:
                    default_gateway = ips[1]
                    break
    else:
        if "default" in routing_low:
            for line in routing.splitlines():
                if "default" in line.lower():
                    ips = _extract_ips(line)
                    if ips:
                        default_gateway = ips[0]
                        break

    if default_gateway is None and len(routing_ips) > 1:
        default_gateway = routing_ips[1]

    neighbors = _extract_ips(arp_table)

    interfaces: list[str] = []
    for line in interface_info.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        token = stripped.split()[0].rstrip(":")
        if token and token not in interfaces:
            interfaces.append(token)

    return {
        "host_os": host_os.value,
        "default_gateway": default_gateway,
        "route_count": len(routes),
        "routes": routes[:25],
        "hop_count": len(hops),
        "hops": hops[:30],
        "neighbor_count": len(neighbors),
        "neighbors": neighbors[:50],
        "interfaces": interfaces[:25],
    }
