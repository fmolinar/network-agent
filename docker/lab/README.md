# Docker Lab

This lab creates reproducible Linux-based network scenarios to validate `network-agent` behavior.

## Important OS Note
Docker Compose cannot run native macOS or Windows kernels. This lab uses Linux containers to emulate troubleshooting conditions.
Cross-OS logic is still validated in CI on macOS/Linux/Windows via unit tests.

## Services
- `probe-ubuntu`: Ubuntu probe host
- `probe-alpine`: Alpine probe host
- `probe-dns-broken`: host with intentionally broken DNS resolver
- `probe-isolated`: host on internal-only network with no internet egress
- `web-ok`: healthy local web service
- `dns-ok`: healthy DNS forwarder for normal probes

## Scenarios Generated
The script writes text artifacts compatible with the CLI and engine:
- `ok`
- `dns_failure`
- `isolated_no_internet`

## Run Lab
```bash
docker compose -f docker/lab/docker-compose.yml up -d --wait
```

Generate artifacts:
```bash
./docker/lab/scripts/collect_scenarios.sh
```

Artifacts output directory default:
- `samples/generated/`

Stop lab:
```bash
docker compose -f docker/lab/docker-compose.yml down -v
```
