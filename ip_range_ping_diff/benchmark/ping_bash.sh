#!/usr/bin/env bash
# Bash ping benchmark: pings all hosts (1-254) in two /24 subnets
# using xargs for parallelism.
#
# Usage: ./ping_bash.sh <subnet_a_prefix> <subnet_b_prefix>
# Example: ./ping_bash.sh 192.168.1 192.168.2
#
# Outputs timing results to stdout.

set -euo pipefail

SUBNET_A="${1:-192.168.1}"
SUBNET_B="${2:-192.168.2}"
PARALLELISM="${BENCH_PARALLELISM:-64}"
TIMEOUT="${BENCH_TIMEOUT:-1}"

# Generate list of all IPs to ping (both subnets, octets 1-254)
generate_ips() {
    for octet in $(seq 1 254); do
        echo "${SUBNET_A}.${octet}"
        echo "${SUBNET_B}.${octet}"
    done
}

# Ping a single host; output result line
ping_one() {
    local ip="$1"
    if ping -c 1 -W "$TIMEOUT" "$ip" > /dev/null 2>&1; then
        echo "UP $ip"
    else
        echo "DOWN $ip"
    fi
}
export -f ping_one
export TIMEOUT

echo "Bash ping benchmark"
echo "Subnets: ${SUBNET_A}.0/24, ${SUBNET_B}.0/24"
echo "Parallelism: ${PARALLELISM}"
echo "Timeout: ${TIMEOUT}s"
echo ""

START_TIME=$(date +%s%N)

# Use xargs for parallel execution
generate_ips | xargs -P "$PARALLELISM" -I {} bash -c 'ping_one "$@"' _ {}

END_TIME=$(date +%s%N)

# Compute elapsed time in seconds
ELAPSED=$(echo "scale=3; ($END_TIME - $START_TIME) / 1000000000" | bc)

echo ""
echo "Total time: ${ELAPSED}s"
echo "Hosts scanned: 508"
