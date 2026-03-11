from __future__ import annotations

import platform
from enum import Enum


class HostOS(str, Enum):
    MACOS = "macos"
    LINUX = "linux"
    WINDOWS = "windows"
    UNKNOWN = "unknown"


def detect_host_os() -> HostOS:
    system = platform.system().lower()
    if system == "darwin":
        return HostOS.MACOS
    if system == "linux":
        return HostOS.LINUX
    if system == "windows":
        return HostOS.WINDOWS
    return HostOS.UNKNOWN


def parse_host_os(value: str | None) -> HostOS:
    if not value or value == "auto":
        return detect_host_os()
    normalized = value.strip().lower()
    for os_value in HostOS:
        if normalized == os_value.value:
            return os_value
    return HostOS.UNKNOWN
