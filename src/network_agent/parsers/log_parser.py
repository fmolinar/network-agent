from __future__ import annotations

import re
from typing import Any


_PATTERNS = {
    "dns_failure": re.compile(r"(NXDOMAIN|SERVFAIL|temporary failure in name resolution)", re.I),
    "tls_error": re.compile(r"(certificate verify failed|tls handshake failed)", re.I),
    "auth_block": re.compile(r"(blocked by policy|access denied|forbidden)", re.I),
}


def parse_logs(raw: str) -> dict[str, Any]:
    return {name: bool(pattern.search(raw)) for name, pattern in _PATTERNS.items()}
