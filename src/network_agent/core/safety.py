from __future__ import annotations

from dataclasses import dataclass

from network_agent.core.host_os import HostOS


@dataclass(slots=True)
class SafetyGate:
    allowed_commands: set[str]
    config_only_commands: set[str]
    dual_use_commands: set[str]
    mutation_tokens: set[str]
    forbidden_tokens: set[str]

    @classmethod
    def default(cls, host_os: HostOS) -> "SafetyGate":
        diagnostics_by_os = {
            HostOS.LINUX: {
                "ping",
                "traceroute",
                "nslookup",
                "dig",
                "ip",
                "ss",
                "netstat",
                "resolvectl",
                "tcpdump",
                "route",
                "arp",
                "ifconfig",
            },
            HostOS.MACOS: {
                "ping",
                "traceroute",
                "nslookup",
                "dig",
                "route",
                "netstat",
                "scutil",
                "networksetup",
                "tcpdump",
                "arp",
                "ifconfig",
            },
            HostOS.WINDOWS: {"ping", "tracert", "nslookup", "ipconfig", "route", "netstat", "powershell", "arp"},
            HostOS.UNKNOWN: {"ping", "traceroute", "tracert", "nslookup", "dig", "netstat", "tcpdump", "arp"},
        }
        dual_use = {"ip", "ifconfig", "route", "netsh", "networksetup", "powershell"}
        return cls(
            allowed_commands=diagnostics_by_os[host_os],
            config_only_commands={"iptables", "ufw", "nmcli", "set-netipaddress", "new-netroute"},
            dual_use_commands=dual_use,
            mutation_tokens={
                "add",
                "set",
                "delete",
                "del",
                "renew",
                "release",
                "flush",
                "replace",
                "change",
                "disable",
                "enable",
                "down",
                "up",
                "new",
                "remove",
            },
            forbidden_tokens={
                "rm",
                "sudo",
                "shutdown",
                "reboot",
                "mkfs",
                "dd",
                "del",
                "format",
                "remove-item",
            },
        )

    def check_command(self, command: str, user_approved: bool = False) -> tuple[bool, str | None]:
        parts = command.strip().split()
        if not parts:
            return False, "empty command"

        lowered_tokens = [p.lower() for p in parts]
        head = lowered_tokens[0]

        if head in self.config_only_commands:
            if user_approved:
                return True, None
            return False, f"approval required for configuration command: {head}"

        if head not in self.allowed_commands:
            return False, f"command not whitelisted: {head}"

        for token in lowered_tokens:
            if token in self.forbidden_tokens:
                return False, f"forbidden token detected: {token}"

        if head in self.dual_use_commands and any(token in self.mutation_tokens for token in lowered_tokens[1:]):
            if user_approved:
                return True, None
            return False, f"approval required for potential configuration change: {command}"

        return True, None

    def is_allowed(self, command: str) -> tuple[bool, str | None]:
        return self.check_command(command, user_approved=False)
