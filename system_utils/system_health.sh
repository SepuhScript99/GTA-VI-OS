#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) System Health
# Evaluates system health against predefined thresholds.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

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
    check_dependencies "awk" "free" "df" "cat" "systemctl"
}

# --- Metric Functions ---

check_cpu() {
    if [ ! -f /proc/stat ]; then
        echo "[SKIP] /proc/stat not found"
        return 2
    fi
    local idle
    idle=$(awk '/^cpu /{print $5}' /proc/stat 2>/dev/null || echo "")
    local total
    total=$(awk '/^cpu /{print $2+$3+$4+$5+$6+$7+$8}' /proc/stat 2>/dev/null || echo "")

    if [ -z "$idle" ] || [ -z "$total" ] || [ "$total" -le 0 ]; then
        echo "[SKIP] Unable to read CPU stats"
        return 2
    fi
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
    if [ ! -f /proc/meminfo ]; then
        echo "[SKIP] /proc/meminfo not found"
        return 2
    fi
    local total available used pct
    total=$(awk '/MemTotal/{print $2}' /proc/meminfo 2>/dev/null || echo "")
    available=$(awk '/MemAvailable/{print $2}' /proc/meminfo 2>/dev/null || echo "")
    if [ -z "$total" ] || [ -z "$available" ] || [ "$total" -le 0 ]; then
        echo "[SKIP] Unable to read memory stats"
        return 2
    fi
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
    if ! failed=$(systemctl --failed --no-legend 2>/dev/null | wc -l); then
        echo "[WARN] Could not check services (systemctl unavailable or permission denied)"
        return 2
    fi

    if [ "$failed" -gt 0 ]; then
        echo "[FAIL] $failed failed service(s)"
        systemctl --failed --no-legend 2>/dev/null | head -5 | while read -r line; do
            echo "  $line"
        done
        return 1
    else
        echo "[OK] No failed services"
        return 0
    fi
}

check_temperature() {
    local temp
    local temp_file

    for f in /sys/class/thermal/thermal_zone0/temp /sys/class/hwmon/hwmon0/temp1_input; do
        if [ -f "$f" ]; then
            temp_file="$f"
            break
        fi
    done

    if [ -z "${temp_file:-}" ]; then
        echo "[SKIP] No temperature sensor found"
        return 2
    fi

    temp=$(cat "$temp_file" 2>/dev/null)
    if [ -z "${temp:-}" ]; then
        echo "[WARN] Could not read temperature sensor"
        return 2
    fi

    local temp_c=$((temp / 1000))

    if [ "$temp_c" -gt "$THRESH_TEMP" ]; then
        echo "[FAIL] Temperature is ${temp_c}C (Threshold: ${THRESH_TEMP}C)"
        return 1
    else
        echo "[OK] Temperature is ${temp_c}C"
        return 0
    fi
}

check_battery() {
    local bat_path
    bat_path=$(find /sys/class/power_supply/ -name "BAT*" -type d 2>/dev/null | head -n 1)

    if [ -z "$bat_path" ]; then
        echo "[SKIP] No battery detected"
        return 2
    fi

    local charge_now charge_full status
    charge_now=$(cat "$bat_path/charge_now" 2>/dev/null || cat "$bat_path/energy_now" 2>/dev/null || echo "")
    charge_full=$(cat "$bat_path/charge_full" 2>/dev/null || cat "$bat_path/energy_full" 2>/dev/null || echo "")
    status=$(cat "$bat_path/status" 2>/dev/null || echo "Unknown")

    if [ -z "$charge_now" ] || [ -z "$charge_full" ] || [ "$charge_full" -eq 0 ]; then
        echo "[SKIP] Battery charge data unavailable"
        return 2
    fi

    local pct=$((charge_now * 100 / charge_full))
    echo "[OK] Battery at ${pct}% (Status: $status)"
    return 0
}

check_swap() {
    local swap_total swap_free swap_used_pct
    swap_total=$(awk '/^SwapTotal/{print $2}' /proc/meminfo 2>/dev/null || echo "0")
    swap_free=$(awk '/^SwapFree/{print $2}' /proc/meminfo 2>/dev/null || echo "0")

    if [ "$swap_total" -eq 0 ]; then
        echo "[SKIP] No swap configured"
        return 2
    fi

    swap_used_pct=$(( (swap_total - swap_free) * 100 / swap_total ))
    if [ "$swap_used_pct" -gt 80 ]; then
        echo "[WARN] Swap usage is ${swap_used_pct}% (High swap usage may indicate memory pressure)"
        return 1
    else
        echo "[OK] Swap usage is ${swap_used_pct}%"
        return 0
    fi
}

check_network() {
    if ping -c 1 -W 3 8.8.8.8 > /dev/null 2>&1; then
        echo "[OK] Network connectivity: internet reachable"
        return 0
    elif ping -c 1 -W 3 192.168.1.1 > /dev/null 2>&1; then
        echo "[WARN] Network connectivity: local network reachable, internet unreachable"
        return 1
    else
        echo "[FAIL] Network connectivity: no network access"
        return 1
    fi
}

# --- Full Health Check ---

full_check() {
    log_info "System Health Check:"
    echo "==================================="

    local passed=0
    local failed=0
    local skipped=0

    echo "1. CPU:"
    if check_cpu; then passed=$((passed + 1)); else failed=$((failed + 1)); fi

    echo "2. Memory:"
    if check_memory; then passed=$((passed + 1)); else failed=$((failed + 1)); fi

    echo "3. Disk:"
    if check_disk; then passed=$((passed + 1)); else failed=$((failed + 1)); fi

    echo "4. Services:"
    local svc_result
    svc_result=$(check_services; echo $?)
    if [ "$svc_result" = "0" ]; then passed=$((passed + 1))
    elif [ "$svc_result" = "2" ]; then skipped=$((skipped + 1))
    else failed=$((failed + 1)); fi

    echo "5. Temperature:"
    local temp_result
    temp_result=$(check_temperature; echo $?)
    if [ "$temp_result" = "0" ]; then passed=$((passed + 1))
    elif [ "$temp_result" = "2" ]; then skipped=$((skipped + 1))
    else failed=$((failed + 1)); fi

    echo "6. Battery:"
    local bat_result
    bat_result=$(check_battery; echo $?)
    if [ "$bat_result" = "0" ]; then passed=$((passed + 1))
    elif [ "$bat_result" = "2" ]; then skipped=$((skipped + 1))
    else failed=$((failed + 1)); fi

    echo "7. Swap:"
    local swap_result
    swap_result=$(check_swap; echo $?)
    if [ "$swap_result" = "0" ]; then passed=$((passed + 1))
    elif [ "$swap_result" = "2" ]; then skipped=$((skipped + 1))
    else failed=$((failed + 1)); fi

    echo "8. Network:"
    local net_result
    net_result=$(check_network; echo $?)
    if [ "$net_result" = "0" ]; then passed=$((passed + 1))
    else failed=$((failed + 1)); fi

    echo "==================================="
    echo "Summary: $passed passed, $failed failed, $skipped skipped."

    if [ "$failed" -gt 0 ]; then
        log_warn "System health check failed: $failed check(s) did not pass."
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
  services                  Check for failed systemd services
  temperature               Check system temperature
  battery                   Check battery status (laptops)
  swap                      Check swap usage
  network                   Check network connectivity
  full                      Run all health checks
  help                      Show this help message

Thresholds:
  CPU > ${THRESH_CPU}%, Memory > ${THRESH_MEM}%, Disk > ${THRESH_DISK}%, Temp > ${THRESH_TEMP}C

Exit codes:
  0 = healthy / check passed
  1 = unhealthy / check failed
  2 = skip (not applicable, e.g., no battery on desktop)

Examples:
  $0 cpu
  $0 full
HELP
}

# --- Main ---

main() {
    if [ "${1:-}" = "help" ] || [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
        show_help
        exit 0
    fi

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
        temperature|temp)
            check_temperature
            ;;
        battery|bat)
            check_battery
            ;;
        swap)
            check_swap
            ;;
        network|net)
            check_network
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