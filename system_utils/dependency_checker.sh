#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Dependency Checker
# Verifies installed packages, command availability, and library dependencies.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
PACKAGES_FILE="/usr/share/vice-os/packages.list"
USER_PACKAGES_FILE="${WORKDIR}/config/packages.list"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Dependency check failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_checker_deps() {
    check_dependencies "dpkg" "command"
}

# --- Package Verification Functions ---

check_package_installed() {
    local package="$1"
    
    if dpkg -s "$package" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

check_packages_from_list() {
    local list_file="${1:-$PACKAGES_FILE}"
    
    if [ ! -f "$list_file" ]; then
        log_error "Package list not found: $list_file"
        return 1
    fi
    
    log_info "Checking packages from: $list_file"
    echo "==================================="
    
    local installed=0
    local missing=0
    local total=0
    
    while IFS= read -r package; do
        # Skip comments and empty lines
        if [[ "$package" =~ ^[[:space:]]*# || -z "$package" ]]; then
            continue
        fi
        
        total=$((total + 1))
        
        if check_package_installed "$package"; then
            installed=$((installed + 1))
        else
            echo "  [MISSING] $package"
            missing=$((missing + 1))
        fi
    done < "$list_file"
    
    echo "==================================="
    echo "Total: $total"
    echo "Installed: $installed"
    echo "Missing: $missing"
    
    if [ "$missing" -gt 0 ]; then
        log_warn "$missing package(s) are missing."
        return 1
    else
        log_success "All $installed packages are installed."
        return 0
    fi
}

# --- Command Verification Functions ---

check_command_available() {
    local cmd="$1"
    
    if command -v "$cmd" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

check_essential_commands() {
    log_info "Checking Essential Commands:"
    echo "==================================="
    
    local commands=(
        "bash" "sh" "apt" "apt-get" "dpkg" "systemctl" "journalctl" "udevadm"
        "ip" "ping" "ss" "nmcli" "conntrack" "blkid" "lsblk" "mount" "umount"
        "xrandr" "xinput" "setxkbmap" "feh" "picom" "notify-send" "pactl"
        "useradd" "usermod" "userdel" "groupadd" "passwd" "su" "sudo" "visudo"
        "tar" "gzip" "bzip2" "xz" "zip" "unzip" "rsync" "find" "grep" "awk" "sed"
        "xterm" "firefox" "thunar" "geany" "geany"
    )
    
    local found=0
    local missing=0
    
    for cmd in "${commands[@]}"; do
        if check_command_available "$cmd"; then
            found=$((found + 1))
        else
            echo "  [MISSING] $cmd"
            missing=$((missing + 1))
        fi
    done
    
    echo "==================================="
    echo "Found: $found"
    echo "Missing: $missing"
    
    if [ "$missing" -gt 0 ]; then
        log_warn "$missing command(s) are missing."
        return 1
    else
        log_success "All $found commands are available."
        return 0
    fi
}

# --- System Service Verification ---

check_critical_services() {
    log_info "Checking Critical Services:"
    echo "==================================="
    
    local services=(
        "NetworkManager" "systemd-resolved" "dbus" "cron" "systemd-journald"
        "ufw" "polkit" "systemd-logind" "systemd-udevd"
    )
    
    local running=0
    local stopped=0
    
    for svc in "${services[@]}"; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            running=$((running + 1))
        else
            echo "  [STOPPED] $svc"
            stopped=$((stopped + 1))
        fi
    done
    
    echo "==================================="
    echo "Running: $running"
    echo "Stopped: $stopped"
    
    if [ "$stopped" -gt 0 ]; then
        log_warn "$stopped service(s) are not running."
        return 1
    else
        log_success "All $running critical services are running."
        return 0
    fi
}

# --- Library Verification Functions ---

check_libraries() {
    log_info "Checking Shared Libraries:"
    echo "==================================="
    
    local libs=(
        "libGL.so.1" "libEGL.so.1" "libxkbcommon.so.0" "libwayland-server.so.0"
        "libpipewire-0.3.so.0" "libpulse.so.0" "libnotify.so.4" "libudev.so.1"
        "libcrypto.so.3" "libssl.so.3" "libcurl.so.4" "libdbus-1.so.3"
        "libX11.so.6" "libxcb.so.1" "libGL.so.1" "libQt5Core.so.5" "libgtk-3.so.0"
    ]
    
    local found=0
    local missing=0
    
    for lib in "${libs[@]}"; do
        if ldconfig -p 2>/dev/null | grep -q "$lib"; then
            found=$((found + 1))
        else
            echo "  [MISSING] $lib"
            missing=$((missing + 1))
        fi
    done
    
    echo "==================================="
    echo "Found: $found"
    echo "Missing: $missing"
}

# --- Full System Audit ---

full_audit() {
    log_info "=== Full Dependency Audit ==="
    echo ""
    
    local passed=0
    local failed=0
    
    # 1. Package verification
    echo "1. Package Verification:"
    if check_packages_from_list; then
        passed=$((passed + 1))
    else
        failed=$((failed + 1))
    fi
    echo ""
    
    # 2. Command availability
    echo "2. Command Availability:"
    if check_essential_commands; then
        passed=$((passed + 1))
    else
        failed=$((failed + 1))
    fi
    echo ""
    
    # 3. Critical services
    echo "3. Critical Services:"
    if check_critical_services; then
        passed=$((passed + 1))
    else
        failed=$((failed + 1))
    fi
    echo ""
    
    # 4. Library check
    echo "4. Shared Libraries:"
    if check_libraries; then
        passed=$((passed + 1))
    else
        failed=$((failed + 1))
    fi
    echo ""
    
    echo "=== Audit Summary ==="
    echo "Passed: $passed"
    echo "Failed: $failed"
    
    if [ "$failed" -gt 0 ]; then
        log_warn "$failed audit(s) failed. System may have missing dependencies."
        return 1
    else
        log_success "All $passed audits passed. System is fully configured."
        return 0
    fi
}

# --- Repair Functions ---

repair_missing() {
    log_info "Checking for missing packages and attempting repair..."
    echo "==================================="
    
    local repaired=0
    
    if [ ! -f "$PACKAGES_FILE" ]; then
        PACKAGES_FILE="$USER_PACKAGES_FILE"
    fi
    
    if [ ! -f "$PACKAGES_FILE" ]; then
        log_error "Package list not found."
        return 1
    fi
    
    while IFS= read -r package; do
        if [[ "$package" =~ ^[[:space:]]*# || -z "$package" ]]; then
            continue
        fi
        
        if ! check_package_installed "$package"; then
            log_info "Attempting to install: $package"
            if apt-get install -y "$package" > /dev/null 2>&1; then
                log_success "Installed: $package"
                repaired=$((repaired + 1))
            else
                log_error "Failed to install: $package"
            fi
        fi
    done < "$PACKAGES_FILE"
    
    if [ "$repaired" -eq 0 ]; then
        log_info "No missing packages to repair."
    else
        log_success "Repaired $repaired package(s)."
    fi
    
    echo "==================================="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Dependency Checker

Usage: $0 <command> [options]

Package Verification:
  packages [list_file]        Check packages against installed list
  repair                      Attempt to install missing packages

Command Verification:
  commands                    Check essential system commands are available

Service Verification:
  services                    Check critical system services are running

Library Verification:
  libraries                   Check shared libraries are available

Full Audit:
  audit                       Run all checks (packages, commands, services, libs)
  help                        Show this help message

Notes:
  - Default package list: $PACKAGES_FILE
  - Repair requires root privileges (use sudo).
  - The audit is non-destructive and safe to run at any time.

Examples:
  $0 packages
  $0 commands
  $0 services
  $0 audit
  $0 repair
HELP
}

# --- Main ---

main() {
    check_checker_deps
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        packages|check-packages)
            local list_file="${1:-$PACKAGES_FILE}"
            check_packages_from_list "$list_file"
            ;;
        commands|check-commands)
            check_essential_commands
            ;;
        services|check-services)
            check_critical_services
            ;;
        libraries|check-libs)
            check_libraries
            ;;
        audit|full-audit)
            full_audit
            ;;
        repair|fix)
            repair_missing
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