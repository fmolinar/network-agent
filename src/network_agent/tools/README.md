# Tools

## WhitelistedShellRunner
A strict shell wrapper for network diagnostics.

Safety behavior:
- validates command head against OS-specific allowlist
- scans for forbidden/destructive tokens
- enforces approval gate for config-changing command patterns
- applies timeout and captures output

By default, the agent uses pre-collected artifacts. With live collection enabled, the runner executes safe read-only checks for missing inputs.
