# Sample Artifacts

This directory contains synthetic troubleshooting inputs for end-to-end tests and demos.

Each scenario folder includes:
- `prompt.txt`
- `ping.txt`
- `traceroute.txt`
- `logs.txt`
- `pcap_summary.txt`
- `expected.json`

Run a sample through CLI:
```bash
network-agent \
  --prompt "$(cat samples/dns_failure/prompt.txt)" \
  --host-os linux \
  --ping samples/dns_failure/ping.txt \
  --traceroute samples/dns_failure/traceroute.txt \
  --logs samples/dns_failure/logs.txt \
  --pcap-summary samples/dns_failure/pcap_summary.txt
```

Generated lab data from Docker Compose is written to `samples/generated/`.
