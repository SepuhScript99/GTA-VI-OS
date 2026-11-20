#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Auto-update Script
# Triggered by vp-autoupdate.timer or manually.
# Logs directly to journald via systemd.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

LOCKFILE="/var/lock/vp-autoupdate.lock"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ -f "$LOCKFILE" ]; then
        rm -f "$LOCKFILE"
    fi
    if [ $exit_code -eq 0 ]; then
        log_success "=== Automatic update complete ==="
    else
        log_error "=== Automatic update failed with exit code $exit_code ==="
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

check_network() {
    log_info "Checking internet connection..."
    # Use DNS resolution check via getent (part of libc-bin, always installed)
    if ! getent hosts deb.debian.org > /dev/null 2>&1; then
        log_warn "No internet connection (DNS resolution failed). Aborting update."
        exit 0 # Exit gracefully, timer will try again tomorrow
    fi
}

# --- Main ---
show_help() {
    cat <<HELP
GTA VI OS Automatic Update Utility

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

    # Prevent concurrent execution
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        log_warn "Another instance of vp-autoupdate is already running. Exiting."
        exit 0
    fi

    log_info "=== Starting Vice OS automatic update ==="

    check_network

    # Options to handle locks, timeouts, and retries
    local APT_OPTS=(
        "-o" "Acquire::Retries=3"
        "-o" "Acquire::http::Timeout=30"
        "-o" "Acquire::https::Timeout=30"
        "-o" "Dpkg::Lock::Timeout=120"
    )

    log_info "Updating package lists..."
    # If update fails (e.g., temporary mirror issue), proceed with upgrade anyway
    # using the last known good lists.
    if ! apt-get "${APT_OPTS[@]}" update -qq; then
        log_warn "apt-get update failed. Proceeding with existing package lists."
    fi

    log_info "Upgrading packages..."
    if ! apt-get "${APT_OPTS[@]}" upgrade -y -qq; then
        log_error "apt-get upgrade failed."
        exit 1
    fi

    log_info "Cleaning up unused dependencies..."
    # Autoremove is safe to fail without aborting the whole script
    apt-get "${APT_OPTS[@]}" autoremove -y -qq || log_warn "apt-get autoremove failed."
}

main "$@"