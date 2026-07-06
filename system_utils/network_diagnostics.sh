#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Network Diagnostics
# Provides comprehensive network troubleshooting utilities including ping,
# traceroute, DNS diagnostics, port scanning, and connection auditing.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
PING_CMD="ping"
TRACEROUTE_CMD="traceroute"
DIG_CMD="dig"
SS_CMD="ss"
IP_CMD="ip"
CURL_CMD="curl"
UFW_CMD="ufw"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Network diagnostics failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_diag_deps() {
    check_dependencies "ping" "ip" "ss"
    
    if ! command -v "$TRACEROUTE_CMD" > /dev/null 2>&1; then
        log_warn "traceroute not found. Install 'traceroute' for route tracing."
    fi
    
    if ! command -v "$DIG_CMD" > /dev/null 2>&1; then
        log_warn "dig not found. DNS diagnostics will use 'getent' fallback."
    fi
    
    if ! command -v "$CURL_CMD" > /dev/null 2>&1; then
        log_warn "curl not found. HTTP testing will be limited."
    fi
}

# --- Ping Testing Functions ---

ping_test() {
    local host="${1:-deb.debian.org}"
    local count="${2:-4}"
    local interval="${3:-1}"
    
    log_info "Pinging $host ($count packets, ${interval}s interval)..."
    echo "==================================="
    
    if ! "$PING_CMD" -c "$count" -i "$interval" -W 5 "$host" 2>&1; then
        log_error "Ping to $host failed."
        return 1
    fi
    
    echo "==================================="
}

multi_ping() {
    local hosts=("${@:-deb.debian.org 8.8.8.8 1.1.1.1}")
    
    log_info "Multi-host Ping Test:"
    echo "==================================="
    
    for host in "${hosts[@]}"; do
        local result
        result=$("$PING_CMD" -c 1 -W 3 "$host" 2>/dev/null)
        local status
        if [ $? -eq 0 ]; then
            local rtt
            rtt=$(echo "$result" | grep "rtt min" | awk -F'/' '{print $5}')
            printf "  %-20s [OK] %sms\n" "$host" "$rtt"
        else
            printf "  %-20s [FAIL]\n" "$host"
        fi
    done
    
    echo "==================================="
}

# --- Traceroute Functions ---

trace_route() {
    local host="${1:-deb.debian.org}"
    local max_hops="${2:-15}"
    
    check_dependencies "traceroute"
    
    log_info "Tracing route to $host (max $max_hops hops)..."
    echo "==================================="
    
    "$TRACEROUTE_CMD" -m "$max_hops" -w 2 -q 1 "$host" 2>&1 || log_warn "Traceroute completed with possible timeouts."
    
    echo "==================================="
}

# --- DNS Diagnostics ---

dns_lookup() {
    local domain="${1:-deb.debian.org}"
    
    log_info "DNS Lookup for: $domain"
    echo "==================================="
    
    if command -v "$DIG_CMD" > /dev/null 2>&1; then
        "$DIG_CMD" "$domain" +short 2>/dev/null || true
        echo ""
        "$DIG_CMD" "$domain" ANY +short 2>/dev/null || true
    else
        log_info "dig not found. Using getent..."
        getent hosts "$domain" 2>/dev/null || log_error "DNS lookup failed."
    fi
    
    echo "==================================="
}

dns_chain_test() {
    local domain="${1:-deb.debian.org}"
    
    log_info "DNS Chain Test for: $domain"
    echo "==================================="
    
    # Step 1: Check /etc/resolv.conf
    echo "1. DNS Servers in /etc/resolv.conf:"
    grep "nameserver" /etc/resolv.conf 2>/dev/null || echo "   (none found)"
    echo ""
    
    # Step 2: Test DNS resolution
    echo "2. Resolution test:"
    if command -v "$DIG_CMD" > /dev/null 2>&1; then
        "$DIG_CMD" "$domain" +short +time=3 +tries=1 2>/dev/null || echo "   [FAIL] dig resolution failed"
    else
        getent hosts "$domain" > /dev/null 2>&1 && echo "   [OK] Resolved via getent" || echo "   [FAIL] Resolution failed"
    fi
    echo ""
    
    # Step 3: Check /etc/hosts
    echo "3. /etc/hosts check:"
    grep "$domain" /etc/hosts 2>/dev/null && echo "   [FOUND] in /etc/hosts" || echo "   [NOT FOUND] in /etc/hosts"
    
    echo "==================================="
}

# --- Connection/Port Functions ---

list_connections() {
    local protocol="${1:-tcp}"
    
    log_info "Active ${protocol^^} Connections:"
    echo "==================================="
    
    "$SS_CMD" -tuna 2>/dev/null | head -n 30
    
    echo "==================================="
}

list_listening_ports() {
    log_info "Listening Ports:"
    echo "==================================="
    
    "$SS_CMD" -tulnp 2>/dev/null || true
    
    echo "==================================="
}

port_check() {
    local host="$1"
    local port="$2"
    
    if [ -z "$host" ] || [ -z "$port" ]; then
        log_error "Host and port required."
        return 1
    fi
    
    log_info "Checking port $port on $host..."
    
    if command -v nc > /dev/null 2>&1; then
        if nc -z -w 3 "$host" "$port" 2>/dev/null; then
            log_success "Port $port is OPEN on $host."
            return 0
        else
            log_error "Port $port is CLOSED on $host."
            return 1
        fi
    else
        # Fallback using bash /dev/tcp
        if (echo > "/dev/tcp/$host/$port") 2>/dev/null; then
            log_success "Port $port is OPEN on $host."
            return 0
        else
            log_error "Port $port is CLOSED on $host."
            return 1
        fi
    fi
}

# --- Interface/Route Functions ---

show_interfaces() {
    log_info "Network Interfaces:"
    echo "==================================="
    
    "$IP_CMD" -br addr 2>/dev/null || true
    
    echo ""
    echo "Interface Statistics:"
    echo "-----------------------------------"
    
    for iface in /sys/class/net/*; do
        if [ -d "$iface" ]; then
            local name
            name=$(basename "$iface")
            if [ "$name" != "lo" ]; then
                local rx_bytes tx_bytes
                rx_bytes=$(cat "$iface/statistics/rx_bytes" 2>/dev/null || echo "0")
                tx_bytes=$(cat "$iface/statistics/tx_bytes" 2>/dev/null || echo "0")
                printf "  %-10s RX: %10s bytes  TX: %10s bytes\n" "$name" "$rx_bytes" "$tx_bytes"
            fi
        fi
    done
    
    echo "==================================="
}

show_routes() {
    log_info "Routing Table:"
    echo "==================================="
    
    "$IP_CMD" route show 2>/dev/null || true
    
    echo ""
    echo "ARP Table:"
    echo "-----------------------------------"
    "$IP_CMD" neigh show 2>/dev/null || true
    
    echo "==================================="
}

# --- Comprehensive Audit Functions ---

full_audit() {
    log_info "=== Network Configuration Audit ==="
    echo ""
    
    # 1. Interface status
    echo "1. Interface Status:"
    "$IP_CMD" -br addr 2>/dev/null || true
    echo ""
    
    # 2. Default route
    echo "2. Default Route:"
    "$IP_CMD" route show default 2>/dev/null || echo "   (none)"
    echo ""
    
    # 3. DNS configuration
    echo "3. DNS Configuration:"
    cat /etc/resolv.conf 2>/dev/null || echo "   (none)"
    echo ""
    
    # 4. Firewall status
    echo "4. Firewall (UFW) Status:"
    if command -v "$UFW_CMD" > /dev/null 2>&1; then
        "$UFW_CMD" status 2>/dev/null || true
    else
        echo "   UFW not installed."
    fi
    echo ""
    
    # 5. Listening ports
    echo "5. Listening Ports (top 10):"
    "$SS_CMD" -tulnp 2>/dev/null | head -n 11 || true
    echo ""
    
    # 6. Connectivity test
    echo "6. Connectivity Test:"
    local passed=0
    local failed=0
    
    for host in "deb.debian.org" "8.8.8.8" "1.1.1.1"; do
        if "$PING_CMD" -c 1 -W 3 "$host" > /dev/null 2>&1; then
            echo "   [OK] $host"
            passed=$((passed + 1))
        else
            echo "   [FAIL] $host"
            failed=$((failed + 1))
        fi
    done
    
    echo ""
    echo "Summary: $passed passed, $failed failed"
    echo ""
    
    # 7. DNS test
    echo "7. DNS Resolution Test:"
    if getent hosts deb.debian.org > /dev/null 2>&1; then
        echo "   [OK] DNS resolution working"
    else
        echo "   [FAIL] DNS resolution failed"
    fi
    
    echo ""
    echo "=== Audit Complete ==="
}

# --- Bandwidth Test Functions ---

bandwidth_test() {
    local duration="${1:-10}"
    
    if ! command -v "$CURL_CMD" > /dev/null 2>&1; then
        log_error "curl not found. Cannot run bandwidth test."
        return 1
    fi
    
    log_info "Running bandwidth test (downloading test file for ${duration}s)..."
    echo "==================================="
    
    # Use Cloudflare's speed test endpoint
    local url="https://speed.cloudflare.com/__down?bytes=10000000"
    
    "$CURL_CMD" -o /dev/null -w "Download Speed: %{speed_download} bytes/s\nTime: %{time_total}s\n" \
        --max-time "$duration" "$url" 2>/dev/null || log_warn "Bandwidth test failed."
    
    echo "==================================="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Network Diagnostics

Usage: $0 <command> [options]

Ping Testing:
  ping [host] [count] [interval]    Ping a host (default: deb.debian.org, 4, 1)
  multi-ping [host1 host2...]      Ping multiple hosts at once

Route Tracing:
  traceroute [host] [max_hops]      Trace route to a host (default: deb.debian.org, 15)

DNS Diagnostics:
  dns [domain]                       DNS lookup for a domain
  dns-chain [domain]                 Full DNS chain test (resolv.conf -> resolution -> hosts)

Connection/Port:
  connections [protocol]             List active connections (tcp/udp)
  ports                             List all listening ports
  port-check <host> <port>          Check if a port is open on a host

Interface/Route:
  interfaces                        Show interface status and statistics
  routes                            Show routing and ARP tables

Audit:
  audit                             Full network configuration audit
  bandwidth [duration]              Quick bandwidth test (default: 10s)

Help:
  help                              Show this help message

Examples:
  $0 ping google.com 4 1
  $0 multi-ping deb.debian.org 8.8.8.8 1.1.1.1
  $0 dns-chain example.com
  $0 port-check example.com 443
  $0 audit
  $0 bandwidth 5
HELP
}

# --- Main ---

main() {
    check_diag_deps
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        ping|ping-test)
            local host="${1:-deb.debian.org}"
            local count="${2:-4}"
            local interval="${3:-1}"
            ping_test "$host" "$count" "$interval"
            ;;
        multi-ping|multi)
            multi_ping "$@"
            ;;
        traceroute|trace)
            local host="${1:-deb.debian.org}"
            local hops="${2:-15}"
            trace_route "$host" "$hops"
            ;;
        dns|dns-lookup)
            local domain="${1:-deb.debian.org}"
            dns_lookup "$domain"
            ;;
        dns-chain|dns-test)
            local domain="${1:-deb.debian.org}"
            dns_chain_test "$domain"
            ;;
        connections|conn)
            local proto="${1:-tcp}"
            list_connections "$proto"
            ;;
        ports|listening)
            list_listening_ports
            ;;
        port-check|port)
            local host="${1:-}"
            local port="${2:-}"
            if [ -z "$host" ] || [ -z "$port" ]; then
                log_error "Host and port required."
                exit 1
            fi
            port_check "$host" "$port"
            ;;
        interfaces|ifaces)
            show_interfaces
            ;;
        routes|routing)
            show_routes
            ;;
        audit|full-audit)
            full_audit
            ;;
        bandwidth|speed-test)
            local duration="${1:-10}"
            bandwidth_test "$duration"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            log_info "Run '$0 help' for usage information."
            exit 1
            ;;
    esac
}

main "$@"