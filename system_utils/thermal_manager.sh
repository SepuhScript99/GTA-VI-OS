#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Thermal Manager
# Provides temperature monitoring, thermal zone listing, and fan speed checks.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Configuration ---
THERMAL_DIR="/sys/class/thermal"
HWMON_DIR="/sys/class/hwmon"
SENSORS_CMD="sensors"

# --- Helper Functions ---

check_thermal_deps() {
    check_dependencies "cat" "find" "grep" "awk"

    # Optional: lm-sensors for detailed output
    if ! command -v "$SENSORS_CMD" > /dev/null 2>&1; then
        log_warn "lm-sensors not found. Detailed output limited. Install 'lm-sensors' for full support."
    fi
}

# Convert millidegrees Celsius to degrees Celsius
millideg_to_celsius() {
    local millideg="$1"
    if [ "$millideg" -eq 0 ]; then
        echo "N/A"
    else
        # Use awk for floating point division
        awk "BEGIN {printf \"%.1f\", $millideg / 1000}"
    fi
}

# --- Information Functions ---

show_status() {
    log_info "Thermal Status:"
    echo "==================================="

    # Try lm-sensors first for detailed output
    if command -v "$SENSORS_CMD" > /dev/null 2>&1; then
        "$SENSORS_CMD" 2>/dev/null || true
    else
        log_info "lm-sensors not installed. Falling back to sysfs."
        list_sysfs_temps
    fi

    echo "==================================="
}

list_sysfs_temps() {
    log_info "Sysfs Thermal Zones:"

    if [ ! -d "$THERMAL_DIR" ]; then
        log_error "Thermal directory $THERMAL_DIR not found."
        return 1
    fi

    local found=false
    for zone in "$THERMAL_DIR"/thermal_zone*; do
        if [ -d "$zone" ]; then
            local zone_name zone_type temp
            zone_name=$(basename "$zone")
            zone_type=$(cat "$zone/type" 2>/dev/null || echo "Unknown")
            temp=$(cat "$zone/temp" 2>/dev/null || echo "0")

            local temp_c
            temp_c=$(millideg_to_celsius "$temp")

            printf "  %-20s %-20s %s°C\n" "$zone_name" "$zone_type" "$temp_c"
            found=true
        fi
    done

    if [ "$found" == false ]; then
        log_warn "No thermal zones found in sysfs."
    fi
}

list_zones() {
    log_info "Available Thermal Zones:"
    echo "==================================="

    if [ ! -d "$THERMAL_DIR" ]; then
        log_error "Thermal directory $THERMAL_DIR not found."
        return 1
    fi

    local found=false
    for zone in "$THERMAL_DIR"/thermal_zone*; do
        if [ -d "$zone" ]; then
            local zone_name zone_type temp
            zone_name=$(basename "$zone")
            zone_type=$(cat "$zone/type" 2>/dev/null || echo "Unknown")
            temp=$(cat "$zone/temp" 2>/dev/null || echo "0")

            local temp_c
            temp_c=$(millideg_to_celsius "$temp")

            echo "  Zone: $zone_name"
            echo "  Type: $zone_type"
            echo "  Temp: ${temp_c}°C"
            echo "  ---"
            found=true
        fi
    done

    if [ "$found" == false ]; then
        log_info "No thermal zones found."
    fi

    echo "==================================="
}

get_cpu_temp() {
    # Try to find CPU temperature from sysfs
    local cpu_temp=""

    # Check x86_pkg_temp or similar
    for zone in "$THERMAL_DIR"/thermal_zone*; do
        if [ -d "$zone" ]; then
            local zone_type
            zone_type=$(cat "$zone/type" 2>/dev/null || echo "")

            if [[ "$zone_type" == *x86_pkg_temp* ]] || [[ "$zone_type" == *cpu* ]] || [[ "$zone_type" == *CPU* ]]; then
                local temp
                temp=$(cat "$zone/temp" 2>/dev/null || echo "0")
                cpu_temp=$(millideg_to_celsius "$temp")
                break
            fi
        fi
    done

    # Fallback: check hwmon
    if [ -z "$cpu_temp" ]; then
        for hwmon in "$HWMON_DIR"/hwmon*; do
            if [ -d "$hwmon" ]; then
                local name
                name=$(cat "$hwmon/name" 2>/dev/null || echo "")

                if [[ "$name" == *coretemp* ]] || [[ "$name" == *k10temp* ]] || [[ "$name" == *cpu_thermal* ]]; then
                    # Read temp1_input (usually the package temp)
                    if [ -f "$hwmon/temp1_input" ]; then
                        local temp
                        temp=$(cat "$hwmon/temp1_input" 2>/dev/null || echo "0")
                        cpu_temp=$(millideg_to_celsius "$temp")
                        break
                    fi
                fi
            fi
        done
    fi

    if [ -z "$cpu_temp" ]; then
        echo "N/A"
    else
        echo "$cpu_temp"
    fi
}

get_fan_speeds() {
    log_info "Fan Speeds:"
    echo "==================================="

    local found=false
    for hwmon in "$HWMON_DIR"/hwmon*; do
        if [ -d "$hwmon" ]; then
            for fan in "$hwmon"/fan*_input; do
                if [ -f "$fan" ]; then
                    local speed
                    speed=$(cat "$fan" 2>/dev/null || echo "0")
                    local fan_name
                    fan_name=$(basename "$fan")
                    local device_name
                    device_name=$(cat "$hwmon/name" 2>/dev/null || echo "Unknown")

                    printf "  %-20s %-15s %s RPM\n" "$device_name" "$fan_name" "$speed"
                    found=true
                fi
            done
        fi
    done

    if [ "$found" == false ]; then
        log_info "No fan sensors found in sysfs."
    fi

    echo "==================================="
}

# --- Monitoring Function ---

monitor_thermal() {
    local interval="${1:-5}"

    if ! [[ "$interval" =~ ^[0-9]+$ ]] || [ "$interval" -lt 1 ]; then
        log_error "Interval must be a positive number (seconds)."
        return 1
    fi

    log_info "Monitoring thermal data (refresh every ${interval}s). Press Ctrl+C to stop."
    echo "==================================="

    while true; do
        clear
        echo "GTA VI OS Thermal Monitor - $(date)"
        echo "==================================="
        echo "CPU Temp: $(get_cpu_temp)°C"
        echo "==================================="

        # Show all zones
        list_sysfs_temps

        echo "==================================="

        # Show fans
        get_fan_speeds

        echo "==================================="
        sleep "$interval"
    done
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Thermal Manager

Usage: $0 <command> [options]

Commands:
  status                     Show full thermal status (uses lm-sensors if available)
  zones                      List all thermal zones from sysfs
  cpu-temp                   Show CPU temperature only
  fans                       Show fan speeds
  monitor [interval]         Continuously monitor temperatures (default: 5s)
  help                       Show this help message

Notes:
  - For detailed sensor output, install 'lm-sensors' and run 'sensors-detect'.
  - Fallback to sysfs (/sys/class/thermal) is automatic if lm-sensors is missing.
  - Fan speed reading depends on hardware support.

Examples:
  $0 status
  $0 cpu-temp
  $0 fans
  $0 monitor 2
HELP
}

# --- Main ---

main() {
    check_thermal_deps

    local command="${1:-help}"
    shift || true

    case "$command" in
        status|info)
            show_status
            ;;
        zones|thermal-zones)
            list_zones
            ;;
        cpu-temp|cpu)
            get_cpu_temp
            ;;
        fans|fan-speeds)
            get_fan_speeds
            ;;
        monitor|watch)
            local interval="${1:-5}"
            monitor_thermal "$interval"
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