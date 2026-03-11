# Contributing

Thanks for contributing to `network-agent`.

## Development Setup
1. Create virtual environment:
   ```bash
   python3 -m venv .venv
   ```
2. Activate it:
   - macOS/Linux: `source .venv/bin/activate`
   - Windows PowerShell: `.venv\\Scripts\\Activate.ps1`
3. Install package + dev deps:
   ```bash
   python -m pip install --upgrade pip
   python -m pip install -e .[dev]
   ```
   This installs the CLI command `network-agent`.

## Run Tests
```bash
python -m pytest -q
```

## CI Expectations
- CI runs on `ubuntu-latest`, `macos-latest`, and `windows-latest`.
- Python versions: `3.10`, `3.11`, `3.12`.
- PRs should pass matrix tests before merge.

## Code Guidelines
- Keep executor checks read-only by default.
- Update safety whitelist/forbidden logic for any new command support.
- Ensure dual-use commands (for example `ip`, `route`, `networksetup`, `powershell`) enforce approval for mutation actions.
- Maintain topology output compatibility when changing route/ARP/interface parsing.
- Keep LLM integration optional and provider-agnostic; default should remain `mock`/disabled for deterministic tests.
- Keep debug mode request-scoped and ensure it never bypasses safety checks.
- Add unit tests for planner/generator/validator logic changes.
- Prefer deterministic parsers and reproducible fixture-based tests.
- Avoid committing secrets in logs or pcap summaries.

## Fixture Workflow
1. Add or update files in `samples/<scenario>/`.
2. Include `expected.json` with expected category and confidence threshold.
3. Add/adjust tests in `tests/` to validate the scenario.

## Docker Lab Workflow
1. Start lab:
   ```bash
   docker compose -f docker/lab/docker-compose.yml up -d --wait
   ```
2. Collect scenario artifacts:
   ```bash
   ./docker/lab/scripts/collect_scenarios.sh
   ```
3. Stop lab:
   ```bash
   docker compose -f docker/lab/docker-compose.yml down -v
   ```

## Pull Request Checklist
- [ ] Tests pass locally
- [ ] New behavior documented in README/docs
- [ ] Safety impact reviewed
- [ ] Fixtures updated when diagnosis behavior changes
- [ ] LLM provider changes include fallback/error handling tests
