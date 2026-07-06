#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Network Manager
# Provides Wi-Fi scanning, connection management, IP reporting, and
# network diagnostics using nmcli and standard networking tools.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
NMCLI_CMD="nmcli"
PING_CMD="ping"
IP_CMD="ip"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Network operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_network_deps() {
    check_dependencies "nmcli" "ip"
}

get_wifi_interface() {
    $NMCLI_CMD -t -f DEVICE,TYPE device | grep "wifi" | head -n 1 | cut -d: -f1
}

get_connected_interface() {
    $NMCLI_CMD -t -f DEVICE,STATE device | grep "connected" | head -n 1 | cut -d: -f1
}

# --- Status Functions ---

show_status() {
    log_info "Network Status"
    echo "==================================="
    
    local active_iface
    active_iface=$(get_connected_interface)
    
    if [ -z "$active_iface" ]; then
        echo "Status:       Disconnected"
        echo "==================================="
        return 0
    fi
    
    local ip_addr gateway dns
    ip_addr=$($IP_CMD addr show "$active_iface" | grep "inet " | awk '{print $2}' | cut -d/ -f1)
    gateway=$($IP_CMD route | grep default | awk '{print $3}' | head -n 1)
    dns=$(grep "nameserver" /etc/resolv.conf | awk '{print $2}' | head -n 1)
    
    echo "Interface:    $active_iface"
    echo "IP Address:   ${ip_addr:-N/A}"
    echo "Gateway:      ${gateway:-N/A}"
    echo "DNS Server:   ${dns:-N/A}"
    echo "==================================="
}

show_ip() {
    local iface="${1:-}"
    
    if [ -z "$iface" ]; then
        iface=$(get_connected_interface)
    fi
    
    if [ -z "$iface" ]; then
        log_error "No connected interface found."
        return 1
    fi
    
    $IP_CMD addr show "$iface" | grep "inet " | awk '{print $2}' | cut -d/ -f1
}

show_interfaces() {
    log_info "Network Interfaces:"
    echo "==================================="
    $NMCLI_CMD device status
    echo "==================================="
}

# --- Wi-Fi Functions ---

scan_wifi() {
    local iface
    iface=$(get_wifi_interface)
    
    if [ -z "$iface" ]; then
        log_error "No Wi-Fi interface found."
        log_info "This system may not have a Wi-Fi adapter."
        return 1
    fi
    
    log_info "Scanning for Wi-Fi networks..."
    $NMCLI_CMD device wifi rescan ifname "$iface" 2>/dev/null || true
    sleep 2
    
    log_info "Available Wi-Fi Networks:"
    echo "==================================="
    $NMCLI_CMD -f SSID,SIGNAL,SECURITY,FREQ device wifi list ifname "$iface"
    echo "==================================="
}

connect_wifi() {
    local ssid="$1"
    local password="${2:-}"
    
    local iface
    iface=$(get_wifi_interface)
    
    if [ -z "$iface" ]; then
        log_error "No Wi-Fi interface found."
        return 1
    fi
    
    log_info "Connecting to Wi-Fi network: $ssid"
    
    if [ -n "$password" ]; then
        if ! $NMCLI_CMD device wifi connect "$ssid" password "$password" ifname "$iface"; then
            log_error "Failed to connect to '$ssid'. Check SSID and password."
            return 1
        fi
    else
        if ! $NMCLI_CMD device wifi connect "$ssid" ifname "$iface"; then
            log_error "Failed to connect to '$ssid'."
            log_info "If this is a secured network, provide a password."
            return 1
        fi
    fi
    
    log_success "Connected to Wi-Fi network: $ssid"
}

disconnect_wifi() {
    local iface
    iface=$(get_wifi_interface)
    
    if [ -z "$iface" ]; then
        log_error "No Wi-Fi interface found."
        return 1
    fi
    
    log_info "Disconnecting from Wi-Fi..."
    $NMCLI_CMD device disconnect "$iface" && log_success "Wi-Fi disconnected." || log_error "Failed to disconnect."
}

show_saved_networks() {
    log_info "Saved Wi-Fi Networks:"
    echo "==================================="
    $NMCLI_CMD -f NAME,UUID,TYPE connection show | grep "wifi" 
    echo "==================================="
}

forget_network() {
    local network_name="$1"
    
    log_info "Forgetting network: $network_name"
    
    if ! $NMCLI_CMD connection delete "$network_name"; then
        log_error "Failed to forget network '$network_name'."
        return 1
    fi
    
    log_success "Network '$network_name' forgotten."
}

# --- Connection Management ---

list_connections() {
    log_info "Network Connections:"
    echo "==================================="
    $NMCLI_CMD connection show
    echo "==================================="
}

activate_connection() {
    local conn_name="$1"
    
    log_info "Activating connection: $conn_name"
    
    if ! $NMCLI_CMD connection up "$conn_name"; then
        log_error "Failed to activate connection '$conn_name'."
        return 1
    fi
    
    log_success "Connection '$conn_name' activated."
}

deactivate_connection() {
    local conn_name="$1"
    
    log_info "Deactivating connection: $conn_name"
    
    if ! $NMCLI_CMD connection down "$conn_name"; then
        log_error "Failed to deactivate connection '$conn_name'."
        return 1
    fi
    
    log_success "Connection '$conn_name' deactivated."
}

# --- Diagnostic Functions ---

ping_test() {
    local host="${1:-deb.debian.org}"
    local count="${2:-4}"
    
    log_info "Pinging $host ($count packets)..."
    
    if ! $PING_CMD -c "$count" -W 5 "$host"; then
        log_error "Ping to $host failed."
        return 1
    fi
    
    log_success "Ping to $host successful."
}

dns_lookup() {
    local domain="${1:-deb.debian.org}"
    
    log_info "Performing DNS lookup for: $domain"
    
    if ! getent hosts "$domain" > /dev/null 2>&1; then
        log_error "DNS lookup failed for $domain."
        return 1
    fi
    
    local ip
    ip=$(getent hosts "$domain" | awk '{print $1}')
    log_success "DNS lookup successful: $domain -> $ip"
}

trace_route() {
    local host="${1:-deb.debian.org}"
    
    check_dependencies "traceroute"
    
    log_info "Tracing route to $host..."
    traceroute -m 15 -w 2 "$host" || log_warn "Traceroute completed with possible timeouts."
}

internet_check() {
    log_info "Checking internet connectivity..."
    
    # Check DNS resolution
    if ! getent hosts deb.debian.org > /dev/null 2>&1; then
        log_error "DNS resolution failed. Cannot resolve deb.debian.org."
        log_info "Check your DNS settings in /etc/resolv.conf"
        return 1
    fi
    
    # Check HTTP connectivity
    if ! curl -s -f -o /dev/null --max-time 5 http://deb.debian.org/debian/Release; then
        log_error "HTTP connectivity check failed."
        log_info "DNS resolves, but cannot reach Debian mirrors."
        log_info "Check firewall rules or network routing."
        return 1
    fi
    
    log_success "Internet connectivity verified."
}

# --- Hotspot Functions ---

create_hotspot() {
    local ssid="$1"
    local password="${2:-}"
    local iface
    iface=$(get_wifi_interface)
    
    if [ -z "$iface" ]; then
        log_error "No Wi-Fi interface found."
        return 1
    fi
    
    log_info "Creating Wi-Fi hotspot: $ssid"
    
    if [ -n "$password" ]; then
        if [ ${#password} -lt 8 ]; then
            log_error "Hotspot password must be at least 8 characters."
            return 1
        fi
        $NMCLI_CMD device wifi hotspot ifname "$iface" ssid "$ssid" password "$password"
    else
        $NMCLI_CMD device wifi hotspot ifname "$iface" ssid "$ssid"
    fi
    
    if [ $? -ne 0 ]; then
        log_error "Failed to create hotspot."
        return 1
    fi
    
    local hotspot_ip
    hotspot_ip=$($IP_CMD addr show "$iface" | grep "inet " | awk '{print $2}' | cut -d/ -f1)
    
    log_success "Hotspot created: $ssid"
    log_info "Hotspot IP: $hotspot_ip"
    log_info "Connect other devices to: $ssid"
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Network Manager

Usage: $0 <command> [options]

Status:
  status                     Show current network status
  ip [interface]             Show IP address
  interfaces                 List all network interfaces

Wi-Fi:
  scan                       Scan and list available Wi-Fi networks
  connect <ssid> [password]  Connect to a Wi-Fi network
  disconnect                 Disconnect from Wi-Fi
  saved-networks             List saved Wi-Fi networks
  forget <network_name>      Delete a saved network

Connections:
  list                       List all network connections
  activate <name>            Activate a connection
  deactivate <name>          Deactivate a connection

Diagnostics:
  ping [host] [count]        Ping a host (default: deb.debian.org, 4 packets)
  dns [domain]               Perform DNS lookup (default: deb.debian.org)
  traceroute [host]          Trace route to a host
  internet-check             Full internet connectivity test

Hotspot:
  hotspot <ssid> [password]  Create a Wi-Fi hotspot

Help:
  help                       Show this help message

Examples:
  $0 status
  $0 scan
  $0 connect MyWiFi mypassword
  $0 ping google.com 3
  $0 hotspot MyHotspot mypassword123
HELP
}

# --- Main ---

main() {
    check_network_deps
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        status)
            show_status
            ;;
        ip)
            local iface="${1:-}"
            show_ip "$iface"
            ;;
        interfaces|ifaces)
            show_interfaces
            ;;
        scan|wifi-scan)
            scan_wifi
            ;;
        connect|wifi-connect)
            local ssid="${1:-}"
            local password="${2:-}"
            if [ -z "$ssid" ]; then
                log_error "SSID required."
                log_info "Usage: $0 connect <ssid> [password]"
                exit 1
            fi
            connect_wifi "$ssid" "$password"
            ;;
        disconnect|wifi-disconnect)
            disconnect_wifi
            ;;
        saved-networks)
            show_saved_networks
            ;;
        forget|delete-network)
            local network_name="${1:-}"
            if [ -z "$network_name" ]; then
                log_error "Network name required."
                exit 1
            fi
            forget_network "$network_name"
            ;;
        list|connections)
            list_connections
            ;;
        activate|up)
            local conn_name="${1:-}"
            if [ -z "$conn_name" ]; then
                log_error "Connection name required."
                exit 1
            fi
            activate_connection "$conn_name"
            ;;
        deactivate|down)
            local conn_name="${1:-}"
            if [ -z "$conn_name" ]; then
                log_error "Connection name required."
                exit 1
            fi
            deactivate_connection "$conn_name"
            ;;
        ping)
            local host="${1:-deb.debian.org}"
            local count="${2:-4}"
            ping_test "$host" "$count"
            ;;
        dns|dns-lookup)
            local domain="${1:-deb.debian.org}"
            dns_lookup "$domain"
            ;;
        traceroute|trace)
            local host="${1:-deb.debian.org}"
            trace_route "$host"
            ;;
        internet-check|net-check)
            internet_check
            ;;
        hotspot|create-hotspot)
            local ssid="${1:-}"
            local password="${2:-}"
            if [ -z "$ssid" ]; then
                log_error "SSID required."
                exit 1
            fi
            create_hotspot "$ssid" "$password"
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