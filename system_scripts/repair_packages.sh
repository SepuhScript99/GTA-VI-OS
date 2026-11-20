#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Package Repair Tool
# Fixes broken dependencies, reconfigures half-installed packages, and cleans
# up the apt cache. Can be run from a TTY if the desktop fails to load.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

LOCKFILE="/var/lock/vice-repair-packages.lock"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ -f "$LOCKFILE" ]; then
        rm -f "$LOCKFILE"
    fi
    if [ $exit_code -eq 0 ]; then
        log_success "=== Package Repair Complete ==="
    else
        log_error "=== Package Repair failed with exit code $exit_code ==="
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
show_help() {
    cat <<HELP
GTA VI OS Package Repair Utility

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
    check_dependencies "apt-get" "dpkg"

    # Prevent concurrent execution with apt/timers
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        log_warn "Another package management process is already running. Exiting."
        exit 1
    fi

    log_info "=== Starting Package Repair ==="

    # 1. Fix interrupted dpkg configurations
    # We use `|| true` here because dpkg might return a non-zero code if a package
    # is broken, but we still want to attempt to fix dependencies in the next step.
    log_info "Reconfiguring any half-installed packages..."
    dpkg --configure -a || log_warn "dpkg --configure -a reported errors. Attempting to continue..."

    # 2. Fix broken dependencies
    log_info "Fixing broken dependencies..."
    if ! apt-get install -f -y; then
        log_error "Failed to fix broken dependencies. Manual intervention required."
        exit 1
    fi

    # 3. Clean up unused packages and cache
    log_info "Cleaning up unused dependencies and apt cache..."
    apt-get autoremove -y || log_warn "autoremove failed."
    apt-get clean || log_warn "apt-get clean failed."

    # 4. Update package lists to ensure they are fresh
    log_info "Updating package lists..."
    local APT_OPTS=(
        "-o" "Acquire::Retries=3"
        "-o" "Acquire::http::Timeout=30"
        "-o" "Acquire::https::Timeout=30"
        "-o" "Dpkg::Lock::Timeout=120"
    )
    if ! apt-get "${APT_OPTS[@]}" update; then
        log_error "Failed to update package lists. Check your network connection."
        log_info "If the network is working, try manually: sudo apt-get update"
        exit 1
    fi

    log_success "=== Package Repair Complete ==="
    log_info "It is recommended to reboot the system to ensure all changes take effect."
}

main "$@"