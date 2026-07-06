#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) System Health
# Evaluates system health against predefined thresholds.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd")

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
THRESH_CPU=90
THRESH_MEM=90
THRESH_DISK=90
THRESH_TEMP=80

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "System health check failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_health_deps() {
    check_dependencies "awk" "free" "df" "cat"
}

# --- Metric Functions ---

check_cpu() {
    local idle
    idle=$(awk '/^cpu /{print $5}' /proc/stat)
    local total
    total=$(awk '/^cpu /{print $2+$3+$4+$5+$6+$7+$8}')
    
    local usage
    usage=$(awk "BEGIN {printf \"%.1f\", 100 - ($idle / $total) * 100}")
    
    local int_usage=${usage%.*}
    
    if [ "$int_usage" -gt "$THRESH_CPU" ]; then
        echo "[FAIL] CPU usage is ${usage}% (Threshold: ${THRESH_CPU}%)"
        return 1
    else
        echo "[OK] CPU usage is ${usage}%"
        return 0
    fi
}

check_memory() {
    local total available used pct
    total=$(awk '/MemTotal/{print $2}' /proc/meminfo)
    available=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
    used=$((total - available))
    pct=$(awk "BEGIN {printf \"%.1f\", ($used / $total) * 100}")
    
    local int_pct=${pct%.*}
    
    if [ "$int_pct" -gt "$THRESH_MEM" ]; then
        echo "[FAIL] Memory usage is ${pct}% (Threshold: ${THRESH_MEM}%)"
        return 1
    else
        echo "[OK] Memory usage is ${pct}%"
        return 0
    fi
}

check_disk() {
    local pct
    pct=$(df / | awk 'NR==2 {print $5}' | tr -d '%')
    
    if [ "$pct" -gt "$THRESH_DISK" ]; then
        echo "[FAIL] Disk usage is ${pct}% (Threshold: ${THRESH_DISK}%)"
        return 1
    else
        echo "[OK] Disk usage is ${pct}%"
        return 0
    fi
}

check_services() {
    local failed
    failed=$(systemctl --failed --no-legend 2>/dev/null | wc -l)
    
    if [ "$failed" -gt 0 ]; then
        echo "[FAIL] $failed failed service(s)"
        return 1
    else
        echo "[OK] No failed services"
        return 0
    fi
}

# --- Full Health Check ---

full_check() {
    log_info "System Health Check:"
    echo "==================================="
    
    local passed=0
    local failed=0
    
    echo "1. CPU:"
    if check_cpu; then passed=$((passed + 1)); else failed=$((failed + 1)); fi
    
    echo "2. Memory:"
    if check_memory; then passed=$((passed + 1)); else failed=$((failed + 1)); fi
    
    echo "3. Disk:"
    if check_disk; then passed=$((passed + 1)); else failed=$((failed + 1)); fi
    
    echo "4. Services:"
    if check_services; then passed=$((passed + 1)); else failed=$((failed + 1)); fi
    
    echo "==================================="
    echo "Summary: $passed passed, $failed failed."
    
    if [ "$failed" -gt 0 ]; then
        log_warn "System health check failed."
        return 1
    else
        log_success "All health checks passed."
        return 0
    fi
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) System Health

Usage: $0 <command>

Commands:
  cpu                       Check CPU usage against threshold
  memory                    Check memory usage against threshold
  disk                      Check disk usage against threshold
  services                  Check for failed services
  full                      Run all health checks
  help                      Show this help message

Notes:
  - Thresholds: CPU > ${THRESH_CPU}%, Memory > ${THRESH_MEM}%, Disk > ${THRESH_DISK}%
  - Exit code 0 = healthy, 1 = unhealthy.

Examples:
  $0 cpu
  $0 full
HELP
}

# --- Main ---

main() {
    check_health_deps
    
    local command="${1:-full}"
    shift || true
    
    case "$command" in
        cpu)
            check_cpu
            ;;
        memory|mem)
            check_memory
            ;;
        disk)
            check_disk
            ;;
        services|svc)
            check_services
            ;;
        full|all)
            full_check
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