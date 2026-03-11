#!/usr/bin/env sh
set -eu

OUT_DIR="${1:-samples/generated}"
mkdir -p "$OUT_DIR"/{ok,dns_failure,isolated_no_internet}

compose() {
  docker compose -f docker/lab/docker-compose.yml "$@"
}

exec_probe() {
  service="$1"
  shift
  compose exec -T "$service" sh -lc "$*"
}

cleanup() {
  compose down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

compose up -d --wait web-ok dns-ok probe-ubuntu probe-alpine probe-dns-broken probe-isolated

# Scenario 1: healthy connectivity from ubuntu probe
{
  echo "I can reach internet and local services, verify baseline health."
} > "$OUT_DIR/ok/prompt.txt"
exec_probe probe-ubuntu "ping -c 4 1.1.1.1" > "$OUT_DIR/ok/ping.txt" 2>&1 || true
exec_probe probe-ubuntu "traceroute -n -m 5 1.1.1.1" > "$OUT_DIR/ok/traceroute.txt" 2>&1 || true
exec_probe probe-ubuntu "nslookup google.com" > "$OUT_DIR/ok/logs.txt" 2>&1 || true
cat > "$OUT_DIR/ok/pcap_summary.txt" << 'PCAP'
retransmits=1
resets=0
dns_failures=0
PCAP

# Scenario 2: DNS failure from misconfigured resolver, but ICMP to IP works
{
  echo "Internet by IP works but DNS lookups fail."
} > "$OUT_DIR/dns_failure/prompt.txt"
exec_probe probe-dns-broken "ping -c 4 1.1.1.1" > "$OUT_DIR/dns_failure/ping.txt" 2>&1 || true
exec_probe probe-dns-broken "traceroute -n -m 5 1.1.1.1" > "$OUT_DIR/dns_failure/traceroute.txt" 2>&1 || true
exec_probe probe-dns-broken "nslookup google.com" > "$OUT_DIR/dns_failure/logs.txt" 2>&1 || true
cat > "$OUT_DIR/dns_failure/pcap_summary.txt" << 'PCAP'
retransmits=2
resets=0
dns_failures=8
PCAP

# Scenario 3: No internet from isolated network
{
  echo "I cannot reach the internet from this host."
} > "$OUT_DIR/isolated_no_internet/prompt.txt"
exec_probe probe-isolated "ping -c 4 1.1.1.1" > "$OUT_DIR/isolated_no_internet/ping.txt" 2>&1 || true
exec_probe probe-isolated "traceroute -n -m 5 1.1.1.1" > "$OUT_DIR/isolated_no_internet/traceroute.txt" 2>&1 || true
exec_probe probe-isolated "nslookup google.com || true" > "$OUT_DIR/isolated_no_internet/logs.txt" 2>&1 || true
cat > "$OUT_DIR/isolated_no_internet/pcap_summary.txt" << 'PCAP'
retransmits=25
resets=3
dns_failures=5
PCAP

echo "Generated scenarios in: $OUT_DIR"
