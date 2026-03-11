# Parsers

Included parsers:
- `ping_parser.py`: packet loss and RTT extraction
- `traceroute_parser.py`: hop/timeout analysis
- `log_parser.py`: regex detection for DNS/TLS/policy issues
- `pcap_parser.py`: simple key/value pcap summary ingestion
- `topology_parser.py`: topology snapshot extraction (gateway, routes, hops, ARP neighbors, interfaces)

Parsers are intentionally deterministic and side-effect free.
