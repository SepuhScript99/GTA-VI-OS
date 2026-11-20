#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Firewall Setup Script
# Configures UFW for secure desktop usage (IPv4 & IPv6) persistently.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

LOCKFILE="/var/lock/vice-firewall.lock"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ -f "$LOCKFILE" ]; then
        rm -f "$LOCKFILE"
    fi
    if [ $exit_code -eq 0 ]; then
        log_success "Firewall configuration script completed."
    else
        log_error "Firewall configuration failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
show_help() {
    cat <<HELP
GTA VI OS Firewall Setup Utility

Usage: $0
Options:
  help, --help, -h   Show this help message
HELP
}

main() {
    if [ "${1:-}" = "help" ] || [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
        show_help
        exit 0
    fi

    check_root
    check_dependencies "ufw"

    # Prevent concurrent execution
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        log_warn "Another firewall configuration process is already running. Exiting."
        exit 0
    fi

    log_warn "Configuring Vice OS Firewall (This will RESET existing rules)..."

    # 1. Reset UFW to ensure a clean slate (idempotency)
    log_info "Resetting UFW rules..."
    ufw --force reset >/dev/null 2>&1 || true

    # 2. Ensure IPv6 is enabled in UFW config (handled declaratively by /etc/default/ufw on build,
    # but we enforce it here for runtime safety)
    if ! grep -q "^IPV6=yes" /etc/default/ufw; then
        log_info "Enabling IPv6 in UFW..."
        sed -i 's/^IPV6=no/IPV6=yes/' /etc/default/ufw
    fi

    # 3. Set default policies
    ufw default deny incoming >/dev/null 2>&1 || true
    ufw default allow outgoing >/dev/null 2>&1 || true

    # 4. Explicitly allow loopback traffic (Critical for desktop IPC)
    ufw allow in on lo >/dev/null 2>&1 || true
    ufw allow out on lo >/dev/null 2>&1 || true

    # 5. Persistently drop invalid packets for both IPv4 and IPv6
    log_info "Adding persistent invalid packet dropping rules..."

    local rule4="-A ufw-before-input -m conntrack --ctstate INVALID -j DROP"
    local rule6="-A ufw6-before-input -m conntrack --ctstate INVALID -j DROP"

    if ! grep -q "$rule4" /etc/ufw/before.rules; then
        sed -i "/# End required lines/a $rule4" /etc/ufw/before.rules
    fi
    if ! grep -q "$rule6" /etc/ufw/before6.rules; then
        sed -i "/# End required lines/a $rule6" /etc/ufw/before6.rules
    fi

    # 6. Allow essential services
    log_info "Allowing SSH (port 22)..."
    ufw limit 22/tcp >/dev/null 2>&1 || true

    log_info "Allowing NTP (port 123)..."
    ufw allow 123/udp >/dev/null 2>&1 || true

    log_info "Allowing mDNS (port 5353)..."
    ufw allow 5353/udp >/dev/null 2>&1 || true

    log_info "Allowing Samba (ports 137, 138, 139, 445)..."
    ufw allow 137:139/udp >/dev/null 2>&1 || true
    ufw allow 137:139/tcp >/dev/null 2>&1 || true
    ufw allow 445/tcp >/dev/null 2>&1 || true

    # 7. Enable the firewall (this compiles and loads the ruleset, including the before.rules changes)
    log_info "Enabling UFW..."
    ufw --force enable >/dev/null 2>&1 || true

    log_success "Firewall configured and enabled successfully."
    log_warn "NOTE: If you install Docker later, it bypasses UFW by default. Configure Docker's iptables setting if strict firewalling is required."
}

main "$@"