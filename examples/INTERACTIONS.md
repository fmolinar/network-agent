# Example Interactions (Full Agent Loop)

These interactions were produced by running:

```bash
PYTHONPATH=src python3 demo.py --output-dir examples/interactions
```

Each scenario runs the full loop:
`planner -> executor -> generator -> validator`.

## Interaction 1: DNS Failure
- User prompt:
  - `I can ping 1.1.1.1 but hostnames fail to resolve.`
- Planner category: `dns`
- Top cause: `DNS resolution failure`
- Confidence: `0.82`
- Artifact: `examples/interactions/dns_failure.json`

## Interaction 2: Connectivity Loss
- User prompt:
  - `I cannot reach internet services reliably; pages time out and packet loss looks high.`
- Planner category: `connectivity`
- Top cause: `High packet loss indicates unstable or broken link`
- Confidence: `0.85`
- Artifact: `examples/interactions/connectivity_loss.json`

## Interaction 3: Transport Retransmits
- User prompt:
  - `My webserver is slow; pcap summary shows many retransmissions.`
- Planner category: `transport`
- Top cause: `Transport congestion or drops causing retransmissions`
- Confidence: `0.74`
- Artifact: `examples/interactions/transport_retransmits.json`

## Audit Logs
Per-scenario audit traces are stored in the same folder:
- `audit-dns_failure.log`
- `audit-connectivity_loss.log`
- `audit-transport_retransmits.log`
