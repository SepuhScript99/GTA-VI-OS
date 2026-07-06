#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Bluetooth Manager
# Provides device scanning, pairing, trusting, connecting, and disconnecting
# using bluetoothctl (BlueZ).
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
BTLCTL_CMD="bluetoothctl"
SYSTEMCTL_CMD="systemctl"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Bluetooth operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_bluetooth_deps() {
    check_dependencies "bluetoothctl"
    
    # Check if bluetooth service is running
    if ! $SYSTEMCTL_CMD is-active --quiet bluetooth 2>/dev/null; then
        log_warn "Bluetooth service is not running. Attempting to start..."
        if ! $SYSTEMCTL_CMD start bluetooth 2>/dev/null; then
            log_error "Failed to start bluetooth service."
            log_info "Check if Bluetooth hardware is present."
            exit 1
        fi
    fi
}

validate_mac() {
    local mac="$1"
    if ! [[ "$mac" =~ ^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$ ]]; then
        log_error "Invalid MAC address format: $mac"
        log_info "Expected format: XX:XX:XX:XX:XX:XX"
        return 1
    fi
    return 0
}

# --- Power Functions ---

power_on() {
    log_info "Powering on Bluetooth adapter..."
    if ! echo -e "power on\nquit" | $BTLCTL_CMD > /dev/null 2>&1; then
        log_error "Failed to power on Bluetooth adapter."
        return 1
    fi
    log_success "Bluetooth adapter powered on."
}

power_off() {
    log_info "Powering off Bluetooth adapter..."
    if ! echo -e "power off\nquit" | $BTLCTL_CMD > /dev/null 2>&1; then
        log_error "Failed to power off Bluetooth adapter."
        return 1
    fi
    log_success "Bluetooth adapter powered off."
}

get_power_status() {
    local status
    status=$(echo -e "show\nquit" | $BTLCTL_CMD 2>/dev/null | grep "Powered:" | awk '{print $2}')
    echo "$status"
}

# --- Scanning Functions ---

scan_devices() {
    log_info "Scanning for Bluetooth devices (10 seconds)..."
    
    # Start scan
    echo -e "power on\nscan on\nquit" | $BTLCTL_CMD > /dev/null 2>&1
    
    # Wait for discovery
    sleep 10
    
    # Stop scan and get devices
    local devices
    devices=$(echo -e "scan off\ndevices\nquit" | $BTLCTL_CMD 2>/dev/null | grep "Device" | sed 's/Device //')
    
    if [ -z "$devices" ]; then
        log_warn "No Bluetooth devices found."
        return 1
    fi
    
    log_info "Discovered Devices:"
    echo "==================================="
    echo "$devices"
    echo "==================================="
}

list_paired_devices() {
    log_info "Paired Bluetooth Devices:"
    echo "==================================="
    
    local devices
    devices=$(echo -e "devices Paired\nquit" | $BTLCTL_CMD 2>/dev/null | grep "Device" | sed 's/Device //')
    
    if [ -z "$devices" ]; then
        log_warn "No paired devices found."
        return 1
    fi
    
    echo "$devices"
    echo "==================================="
}

# --- Device Management Functions ---

pair_device() {
    local mac="$1"
    
    validate_mac "$mac" || return 1
    
    log_info "Pairing with device: $mac"
    
    # Set agent to default and attempt pairing
    if ! echo -e "agent on\ndefault-agent\npair $mac\nquit" | $BTLCTL_CMD 2>&1 | grep -q "Pairing successful"; then
        log_error "Failed to pair with $mac."
        log_info "Ensure the device is in pairing mode."
        return 1
    fi
    
    log_success "Successfully paired with $mac."
}

trust_device() {
    local mac="$1"
    
    validate_mac "$mac" || return 1
    
    log_info "Trusting device: $mac"
    
    if ! echo -e "trust $mac\nquit" | $BTLCTL_CMD 2>&1 | grep -q "trust succeeded"; then
        log_error "Failed to trust $mac."
        return 1
    fi
    
    log_success "Device $mac trusted."
}

untrust_device() {
    local mac="$1"
    
    validate_mac "$mac" || return 1
    
    log_info "Untrusting device: $mac"
    
    if ! echo -e "untrust $mac\nquit" | $BTLCTL_CMD > /dev/null 2>&1; then
        log_error "Failed to untrust $mac."
        return 1
    fi
    
    log_success "Device $mac untrusted."
}

connect_device() {
    local mac="$1"
    
    validate_mac "$mac" || return 1
    
    log_info "Connecting to device: $mac"
    
    if ! echo -e "connect $mac\nquit" | $BTLCTL_CMD 2>&1 | grep -q "Connection successful"; then
        log_error "Failed to connect to $mac."
        log_info "Ensure the device is powered on and in range."
        return 1
    fi
    
    log_success "Connected to $mac."
}

disconnect_device() {
    local mac="$1"
    
    validate_mac "$mac" || return 1
    
    log_info "Disconnecting from device: $mac"
    
    if ! echo -e "disconnect $mac\nquit" | $BTLCTL_CMD 2>&1 | grep -q "Disconnected"; then
        log_error "Failed to disconnect from $mac."
        return 1
    fi
    
    log_success "Disconnected from $mac."
}

remove_device() {
    local mac="$1"
    
    validate_mac "$mac" || return 1
    
    log_info "Removing device: $mac"
    
    if ! echo -e "remove $mac\nquit" | $BTLCTL_CMD 2>&1 | grep -q "Device removed"; then
        log_error "Failed to remove $mac."
        return 1
    fi
    
    log_success "Device $mac removed."
}

# --- Information Functions ---

show_device_info() {
    local mac="$1"
    
    validate_mac "$mac" || return 1
    
    log_info "Device Information: $mac"
    echo "==================================="
    echo -e "info $mac\nquit" | $BTLCTL_CMD 2>/dev/null | grep -v "^\[" | grep -v "^Agent" | grep -v "^Menu"
    echo "==================================="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Bluetooth Manager

Usage: $0 <command> [options]

Power:
  power-on                    Power on Bluetooth adapter
  power-off                   Power off Bluetooth adapter
  power-status                Check power status

Scanning:
  scan                        Scan for devices (10 seconds)
  list-paired                 List paired devices

Device Management:
  pair <mac>                  Pair with a device
  trust <mac>                 Trust a paired device
  untrust <mac>               Untrust a device
  connect <mac>               Connect to a paired device
  disconnect <mac>            Disconnect from a device
  remove <mac>                Remove a paired device

Information:
  info <mac>                  Show detailed device information

Help:
  help                        Show this help message

Examples:
  $0 power-on
  $0 scan
  $0 pair AA:BB:CC:DD:EE:FF
  $0 trust AA:BB:CC:DD:EE:FF
  $0 connect AA:BB:CC:DD:EE:FF
  $0 info AA:BB:CC:DD:EE:FF
HELP
}

# --- Main ---

main() {
    check_bluetooth_deps
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        power-on)
            power_on
            ;;
        power-off)
            power_off
            ;;
        power-status)
            local status
            status=$(get_power_status)
            if [ "$status" == "yes" ]; then
                log_info "Bluetooth is powered on."
            else
                log_info "Bluetooth is powered off."
            fi
            ;;
        scan|discover)
            scan_devices
            ;;
        list-paired|paired)
            list_paired_devices
            ;;
        pair)
            local mac="${1:-}"
            if [ -z "$mac" ]; then
                log_error "MAC address required."
                exit 1
            fi
            pair_device "$mac"
            ;;
        trust)
            local mac="${1:-}"
            if [ -z "$mac" ]; then
                log_error "MAC address required."
                exit 1
            fi
            trust_device "$mac"
            ;;
        untrust)
            local mac="${1:-}"
            if [ -z "$mac" ]; then
                log_error "MAC address required."
                exit 1
            fi
            untrust_device "$mac"
            ;;
        connect)
            local mac="${1:-}"
            if [ -z "$mac" ]; then
                log_error "MAC address required."
                exit 1
            fi
            connect_device "$mac"
            ;;
        disconnect)
            local mac="${1:-}"
            if [ -z "$mac" ]; then
                log_error "MAC address required."
                exit 1
            fi
            disconnect_device "$mac"
            ;;
        remove|unpair)
            local mac="${1:-}"
            if [ -z "$mac" ]; then
                log_error "MAC address required."
                exit 1
            fi
            remove_device "$mac"
            ;;
        info|show)
            local mac="${1:-}"
            if [ -z "$mac" ]; then
                log_error "MAC address required."
                exit 1
            fi
            show_device_info "$mac"
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