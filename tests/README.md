# Test Harness

This directory contains unit and synthetic-case tests.

Current coverage:
- planner classification
- platform check mapping (`traceroute` vs `tracert`)
- pipeline integration path
- validator safety gate command blocking
- Windows whitelist acceptance for `tracert`
- approval requirement for configuration-changing commands
- executor live collection fallback path for missing artifacts
- topology snapshot generation from artifacts/live command outputs
- optional LLM critic integration path (mock provider)
- sample fixture regression checks across diagnosis categories
- request debug trace structure and agent operation visibility

Run:
```bash
pytest
```
