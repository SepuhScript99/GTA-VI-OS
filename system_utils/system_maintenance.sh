#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) System Maintenance
# Performs comprehensive system health checks, integrity verification, and audits.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd")

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
DPKG_CMD="dpkg"
DEBSUMS_CMD="debsums"
LOGROTATE_CMD="logrotate"
JOURNALCTL_CMD="journalctl"
SYSTEMCTL_CMD="systemctl"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "System maintenance failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_maintenance_deps() {
    check_dependencies "dpkg" "systemctl" "journalctl"
}

# --- Health Check Functions ---

check_system_health() {
    log_info "System Health Check:"
    echo "==================================="
    
    local passed=0
    local failed=0
    
    # 1. Check systemd failed units
    echo "1. Systemd Failed Units:"
    local failed_units
    failed_units=$("$SYSTEMCTL_CMD" --failed --no-legend 2>/dev/null | awk '{print $1}')
    
    if [ -z "$failed_units" ]; then
        echo "   [OK] No failed units."
        passed=$((passed + 1))
    else
        echo "   [FAIL] Failed units found:"
        echo "$failed_units" | sed 's/^/      /'
        failed=$((failed + 1))
    fi
    echo ""
    
    # 2. Check disk space
    echo "2. Disk Space:"
    local disk_full
    disk_full=$(df -h / | awk 'NR==2 && $5 > 90 {print $5}')
    
    if [ -z "$disk_full" ]; then
        echo "   [OK] Root partition < 90% full."
        passed=$((passed + 1))
    else
        echo "   [FAIL] Root partition is ${disk_full} full."
        failed=$((failed + 1))
    fi
    echo ""
    
    # 3. Check memory
    echo "3. Memory:"
    local mem_available
    mem_available=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
    local mem_total
    mem_total=$(awk '/MemTotal/{print $2}' /proc/meminfo)
    
    if [ "$mem_available" -gt $((mem_total / 10)) ]; then
        echo "   [OK] >10% memory available."
        passed=$((passed + 1))
    else
        echo "   [WARN] <10% memory available."
        failed=$((failed + 1))
    fi
    echo ""
    
    # 4. Check journal size
    echo "4. Journal Size:"
    local journal_size
    journal_size=$("$JOURNALCTL_CMD" --disk-usage 2>/dev/null | awk '{print $1}')
    echo "   Journal: $journal_size"
    passed=$((passed + 1))
    echo ""
    
    # 5. Check last boot time
    echo "5. Last Boot:"
    local uptime
    uptime=$(uptime -p)
    echo "   $uptime"
    passed=$((passed + 1))
    echo ""
    
    echo "Summary: $passed passed, $failed failed."
    
    if [ "$failed" -gt 0 ]; then
        log_warn "Health check found $failed issue(s)."
        return 1
    else
        log_success "All health checks passed."
        return 0
    fi
}

# --- Integrity Verification Functions ---

verify_package_integrity() {
    log_info "Package Integrity Verification:"
    echo "==================================="
    
    if ! command -v "$DEBSUMS_CMD" > /dev/null 2>&1; then
        log_warn "debsums not installed. Install 'debsums' for integrity checking."
        return 1
    fi
    
    local changed_files
    changed_files=$("$DEBSUMS_CMD" -c 2>/dev/null | head -n 20)
    
    if [ -z "$changed_files" ]; then
        log_success "All package files are intact."
        return 0
    else
        log_warn "Changed/missing package files detected:"
        echo "$changed_files" | sed 's/^/  /'
        return 1
    fi
}

verify_dpkg_database() {
    log_info "DPKG Database Audit:"
    echo "==================================="
    
    # Check for broken packages
    local broken
    broken=$("$DPKG_CMD" -l | grep -c "^iF\|^iU\|^iH\|^rc " 2>/dev/null || echo "0")
    
    if [ "$broken" -eq 0 ]; then
        log_success "No broken or half-installed packages."
    else
        log_warn "Found $broken broken/half-installed packages."
        "$DPKG_CMD" -l | grep "^iF\|^iU\|^iH\|^rc " | sed 's/^/  /'
    fi
}

# --- Audit Functions ---

audit_log_rotation() {
    log_info "Log Rotation Audit:"
    echo "==================================="
    
    if ! command -v "$LOGROTATE_CMD" > /dev/null 2>&1; then
        log_warn "logrotate not installed."
        return 1
    fi
    
    # Dry-run logrotate to check for errors
    if "$LOGROTATE_CMD" -d /etc/logrotate.conf 2>&1 | grep -q "error"; then
        log_error "Logrotate configuration has errors."
        "$LOGROTATE_CMD" -d /etc/logrotate.conf 2>&1 | grep "error" | sed 's/^/  /'
        return 1
    else
        log_success "Logrotate configuration is valid."
        return 0
    fi
}

audit_services() {
    log_info "Service Audit:"
    echo "==================================="
    
    # List enabled services
    echo "Enabled Services:"
    "$SYSTEMCTL_CMD" list-unit-files --type=service --state=enabled --no-legend 2>/dev/null | awk '{print "  " $1}
    "$SYSTEMCTL_CMD" list-unit-files --type=service --state=enabled --no-legend 2>/dev/null | awk '{print "  " $1}'
    
    echo ""
    echo "Failed Services:"
    local failed
    failed=$("$SYSTEMCTL_CMD" --failed --no-legend 2>/dev/null)
    
    if [ -z "$failed" ]; then
        echo "  (none)"
    else
        echo "$failed" | sed 's/^/  /'
    fi
    
    echo "==================================="
}

# --- Full Maintenance ---

full_maintenance() {
    log_info "=== Full System Maintenance ==="
    echo ""
    
    local passed=0
    local failed=0
    
    echo "1. System Health:"
    if check_system_health; then
        passed=$((passed + 1))
    else
        failed=$((failed + 1))
    fi
    echo ""
    
    echo "2. Package Integrity:"
    if verify_package_integrity; then
        passed=$((passed + 1))
    else
        failed=$((failed + 1))
    fi
    echo ""
    
    echo "3. DPKG Database:"
    verify_dpkg_database
    echo ""
    
    echo "4. Log Rotation:"
    if audit_log_rotation; then
        passed=$((passed + 1))
    else
        failed=$((failed + 1))
    fi
    echo ""
    
    echo "5. Service Audit:"
    audit_services
    echo ""
    
    echo "=== Maintenance Summary ==="
    echo "Passed: $passed"
    echo "Failed: $failed"
    
    if [ "$failed" -gt 0 ]; then
        log_warn "$failed maintenance check(s) failed."
        return 1
    else
        log_success "All maintenance checks passed."
        return 0
    fi
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) System Maintenance

Usage: $0 <command>

Commands:
  health                    Run system health checks
  integrity                Verify package file integrity (debsums)
  dpkg                     Audit dpkg database for broken packages
  logrotate                Audit logrotate configuration
  services                 Audit enabled and failed services
  full                     Run all maintenance checks
  help                     Show this help message

Notes:
  - Requires root privileges for full functionality (use sudo).
  - Integrity check requires 'debsums' package.

Examples:
  $0 health
  $0 integrity
  $0 full
HELP
}

# --- Main ---

main() {
    check_maintenance_deps
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        health|health-check)
            check_system_health
            ;;
        integrity|verify-integrity)
            verify_package_integrity
            ;;
        dpkg|dpkg-audit)
            verify_dpkg_database
            ;;
        logrotate|log-rotation)
            audit_log_rotation
            ;;
        services|audit-services)
            audit_services
            ;;
        full|all)
            full_maintenance
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