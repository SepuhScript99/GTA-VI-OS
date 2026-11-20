#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Update Manager
# Provides comprehensive, interactive system update capabilities.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Configuration ---
LOG_FILE="/var/log/vice-os-update-manager.log"

# --- Helper Functions ---

check_update_deps() {
    check_dependencies "apt-get" "dpkg"
}

# APT options for safe, non-interactive operations
get_apt_opts() {
    echo "-o" "Acquire::Retries=3"
    echo "-o" "Dpkg::Lock::Timeout=60"
    echo "-o" "Dpkg::Options::=--force-confold"
    echo "-o" "Dpkg::Options::=--force-confdef"
    echo "-y"
}

# --- Core Update Functions ---

do_update() {
    log_info "Updating package lists..."

    local apt_opts
    apt_opts=$(get_apt_opts | tr '\n' ' ')

    if ! apt-get $apt_opts update; then
        log_error "Failed to update package lists."
        log_info "Check your network connection and repository configuration."
        log_info "Try: sudo apt-get update"
        return 1
    fi

    log_success "Package lists updated successfully."
}

do_upgrade() {
    log_info "Upgrading installed packages..."

    do_update || return 1

    local apt_opts
    apt_opts=$(get_apt_opts | tr '\n' ' ')

    if ! apt-get $apt_opts upgrade; then
        log_error "Failed to upgrade packages."
        log_info "This may indicate held packages, dependency conflicts, or disk space."
        log_info "Try: sudo apt-get upgrade or check /var/log/apt/history.log"
        return 1
    fi

    log_success "Package upgrade completed successfully."
}

do_full_upgrade() {
    log_info "Performing full system upgrade (dist-upgrade)..."

    do_update || return 1

    local apt_opts
    apt_opts=$(get_apt_opts | tr '\n' ' ')

    if ! apt-get $apt_opts dist-upgrade; then
        log_error "Failed to perform full upgrade."
        log_info "This may indicate held packages or dependency conflicts."
        log_info "Try: sudo apt-get dist-upgrade or check /var/log/apt/history.log"
        return 1
    fi

    log_success "Full system upgrade completed successfully."
}

do_full_update() {
    log_info "Performing complete system update (update + dist-upgrade + autoremove)..."

    do_full_upgrade || return 1

    log_info "Cleaning up unused packages..."
    local apt_opts
    apt_opts=$(get_apt_opts | tr '\n' ' ')
    apt-get $apt_opts autoremove || log_warn "Autoremove completed with warnings."

    log_success "Complete system update finished."
}

# --- Maintenance Functions ---

clean_cache() {
    log_info "Cleaning APT cache..."

    local apt_opts
    apt_opts=$(get_apt_opts | tr '\n' ' ')

    apt-get $apt_opts clean
    apt-get $apt_opts autoremove

    log_success "APT cache cleaned and unused packages removed."
}

fix_broken() {
    log_info "Fixing broken dependencies..."

    local apt_opts
    apt_opts=$(get_apt_opts | tr '\n' ' ')

    dpkg --configure -a || true
    apt-get $apt_opts install -f || true

    log_success "Dependency repair attempt completed."
}

# --- Information Functions ---

list_upgradable() {
    log_info "Checking for upgradable packages..."

    # Update lists first to get accurate results
    apt-get update -qq > /dev/null 2>&1 || true

    local upgradable
    upgradable=$(apt-get -qq list --upgradable 2>/dev/null | grep -v "Listing")

    if [ -z "$upgradable" ]; then
        log_info "All packages are up to date."
        return 0
    fi

    log_info "Upgradable Packages:"
    echo "==================================="
    echo "$upgradable"
    echo "==================================="
}

show_history() {
    local count="${1:-20}"

    log_info "Package Install/Update History (last $count):"
    echo "==================================="

    if [ -f /var/log/dpkg.log ]; then
        grep -E " install | upgrade " /var/log/dpkg.log | tail -n "$count"
    else
        log_warn "No dpkg history found."
    fi

    echo "==================================="
}

check_updates() {
    log_info "Checking for available updates..."

    # Update lists silently
    apt-get update -qq > /dev/null 2>&1 || true

    local upgradable_count
    upgradable_count=$(apt-get -qq list --upgradable 2>/dev/null | grep -vc "Listing" || echo "0")

    if [ "$upgradable_count" -eq 0 ]; then
        log_success "System is up to date. No updates available."
    else
        log_info "$upgradable_count update(s) are available."
        log_info "Run '$0 list-upgradable' to see them, or '$0 upgrade' to install."
    fi
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Update Manager

Usage: $0 <command> [options]

Update Operations:
  update                      Update package lists only
  upgrade                     Update lists and upgrade packages
  full-upgrade                Update lists and dist-upgrade (handles dependency changes)
  full-update                 Full upgrade + autoremove (recommended for regular use)

Maintenance:
  clean                       Clean APT cache and autoremove unused packages
  fix-broken                  Fix broken dependencies and configure packages

Information:
  list-upgradable             List packages that have updates available
  check-updates               Quick check if updates are available (exit 0=no, 1=yes)
  history [count]             Show package install/update history (default: 20)

Help:
  help                        Show this help message

Examples:
  $0 update
  $0 full-update
  $0 list-upgradable
  $0 check-updates
  $0 history 50
HELP
}

# --- Main ---

main() {
    check_update_deps
    check_root

    local command="${1:-help}"
    shift || true

    case "$command" in
        update)
            do_update
            ;;
        upgrade)
            do_upgrade
            ;;
        full-upgrade|dist-upgrade)
            do_full_upgrade
            ;;
        full-update|complete)
            do_full_update
            ;;
        clean|clean-cache)
            clean_cache
            ;;
        fix-broken|fix)
            fix_broken
            ;;
        list-upgradable|upgradable)
            list_upgradable
            ;;
        check-updates|check)
            check_updates
            ;;
        history|log)
            local count="${1:-20}"
            show_history "$count"
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