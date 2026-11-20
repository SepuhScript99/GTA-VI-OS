#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Battery Manager
# Provides detailed battery diagnostics, health reporting, charging threshold
# management, and calibration guidance for laptop systems.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Configuration ---
POWER_SUPPLY_DIR="/sys/class/power_supply"
BATTERY_NAME="BAT0"
UPOWER_CMD="upower"
ACPI_CMD="acpi"

# --- Helper Functions ---

check_battery_deps() {
    check_dependencies "cat" "grep" "awk"

    # Optional dependencies for extended features
    if ! command -v "$UPOWER_CMD" > /dev/null 2>&1; then
        log_warn "upower not found. Extended battery info unavailable."
    fi
    if ! command -v "$ACPI_CMD" > /dev/null 2>&1; then
        log_warn "acpi not found. Some features may be limited."
    fi
}

find_battery_device() {
    # Try to find any battery device in sysfs
    for device in "$POWER_SUPPLY_DIR"/BAT*; do
        if [ -d "$device" ] && [ -f "$device/type" ]; then
            local type
            type=$(cat "$device/type" 2>/dev/null)
            if [ "$type" == "Battery" ]; then
                echo "$(basename "$device")"
                return 0
            fi
        fi
    done
    return 1
}

get_battery_path() {
    local battery_name="${1:-$BATTERY_NAME}"
    echo "${POWER_SUPPLY_DIR}/${battery_name}"
}

is_battery_present() {
    local battery_name="${1:-$BATTERY_NAME}"
    local battery_path
    battery_path=$(get_battery_path "$battery_name")

    if [ ! -d "$battery_path" ]; then
        return 1
    fi

    if [ ! -f "$battery_path/type" ] || [ "$(cat "$battery_path/type" 2>/dev/null)" != "Battery" ]; then
        return 1
    fi

    return 0
}

# --- Status Functions ---

show_status() {
    local battery_name
    battery_name=$(find_battery_device 2>/dev/null || echo "$BATTERY_NAME")

    if ! is_battery_present "$battery_name"; then
        log_error "No battery found. This system may not have a battery (desktop or VM)."
        return 1
    fi

    local battery_path
    battery_path=$(get_battery_path "$battery_name")

    log_info "Battery Status Report:"
    echo "==================================="

    # Read basic info from sysfs
    local status capacity energy_full energy_full_design voltage_now current_now
    status=$(cat "$battery_path/status" 2>/dev/null || echo "Unknown")
    capacity=$(cat "$battery_path/capacity" 2>/dev/null || echo "N/A")
    energy_full=$(cat "$battery_path/energy_full" 2>/dev/null || echo "0")
    energy_full_design=$(cat "$battery_path/energy_full_design" 2>/dev/null || echo "0")
    voltage_now=$(cat "$battery_path/voltage_now" 2>/dev/null || echo "0")
    current_now=$(cat "$battery_path/current_now" 2>/dev/null || echo "0")

    echo "Device:        $battery_name"
    echo "Status:        $status"
    echo "Capacity:      $capacity%"

    # Calculate health percentage
    if [ "$energy_full" -gt 0 ] && [ "$energy_full_design" -gt 0 ]; then
        local health
        health=$((energy_full * 100 / energy_full_design))
        echo "Health:        $health% (Design: $((energy_full_design / 1000000)) Wh, Full: $((energy_full / 1000000)) Wh)"
    fi

    # Voltage (convert from microvolts to volts)
    if [ "$voltage_now" -gt 0 ]; then
        local voltage
        voltage=$(echo "scale=2; $voltage_now / 1000000" | bc 2>/dev/null || echo "N/A")
        echo "Voltage:       ${voltage}V"
    fi

    # Current (convert from microamps to amps)
    if [ "$current_now" -ne 0 ]; then
        local current
        current=$(echo "scale=2; $current_now / 1000000" | bc 2>/dev/null || echo "N/A")
        echo "Current:       ${current}A"
    fi

    # Try upower for extended info
    if command -v "$UPOWER_CMD" > /dev/null 2>&1; then
        local upower_info
        upower_info=$("$UPOWER_CMD" -i "$("$UPOWER_CMD" -e | grep -i "BAT")" 2>/dev/null || true)

        if [ -n "$upower_info" ]; then
            local vendor model serial
            vendor=$(echo "$upower_info" | grep "vendor:" | sed 's/.*: *//')
            model=$(echo "$upower_info" | grep "model:" | sed 's/.*: *//')
            serial=$(echo "$upower_info" | grep "serial:" | sed 's/.*: *//')

            if [ -n "$vendor" ]; then
                echo "Vendor:        $vendor"
            fi
            if [ -n "$model" ]; then
                echo "Model:         $model"
            fi
            if [ -n "$serial" ]; then
                echo "Serial:        $serial"
            fi

            # Cycle count
            local cycles
            cycles=$(echo "$upower_info" | grep "cycle-count" | awk '{print $2}')
            if [ -n "$cycles" ] && [ "$cycles" != "0" ]; then
                echo "Cycle Count:   $cycles"
            fi

            # Time to empty/full
            if [ "$status" == "Discharging" ]; then
                local time_empty
                time_empty=$(echo "$upower_info" | grep "time to empty" | sed 's/.*: *//')
                if [ -n "$time_empty" ]; then
                    echo "Time to empty: $time_empty"
                fi
            elif [ "$status" == "Charging" ]; then
                local time_full
                time_full=$(echo "$upower_info" | grep "time to full" | sed 's/.*: *//')
                if [ -n "$time_full" ]; then
                    echo "Time to full:  $time_full"
                fi
            fi
        fi
    fi

    echo "==================================="
}

show_health() {
    local battery_name
    battery_name=$(find_battery_device 2>/dev/null || echo "$BATTERY_NAME")

    if ! is_battery_present "$battery_name"; then
        log_error "No battery found."
        return 1
    fi

    local battery_path
    battery_path=$(get_battery_path "$battery_name")

    log_info "Battery Health Report:"
    echo "==================================="

    local energy_full energy_full_design
    energy_full=$(cat "$battery_path/energy_full" 2>/dev/null || echo "0")
    energy_full_design=$(cat "$battery_path/energy_full_design" 2>/dev/null || echo "0")

    if [ "$energy_full" -eq 0 ] || [ "$energy_full_design" -eq 0 ]; then
        log_warn "Health data not available from sysfs."
        log_info "Trying upower..."

        if command -v "$UPOWER_CMD" > /dev/null 2>&1; then
            "$UPOWER_CMD" -i "$("$UPOWER_CMD" -e | grep -i "BAT")" 2>/dev/null | grep -E "energy-full|energy-full-design|capacity"
        else
            log_error "upower not installed. Cannot retrieve health data."
            return 1
        fi
    else
        local health
        health=$((energy_full * 100 / energy_full_design))

        echo "Design Capacity: $((energy_full_design / 1000000)) Wh"
        echo "Full Capacity:   $((energy_full / 1000000)) Wh"
        echo "Health:          $health%"

        if [ "$health" -ge 80 ]; then
            log_success "Battery health is GOOD (>=80%)."
        elif [ "$health" -ge 60 ]; then
            log_warn "Battery health is FAIR (60-79%). Consider replacement soon."
        else
            log_error "Battery health is POOR (<60%). Replacement recommended."
        fi
    fi

    echo "==================================="
}

get_capacity() {
    local battery_name
    battery_name=$(find_battery_device 2>/dev/null || echo "$BATTERY_NAME")

    if ! is_battery_present "$battery_name"; then
        echo "N/A"
        return 1
    fi

    local battery_path
    battery_path=$(get_battery_path "$battery_name")

    cat "$battery_path/capacity" 2>/dev/null || echo "N/A"
}

is_charging() {
    local battery_name
    battery_name=$(find_battery_device 2>/dev/null || echo "$BATTERY_NAME")

    if ! is_battery_present "$battery_name"; then
        return 1
    fi

    local battery_path status
    battery_path=$(get_battery_path "$battery_name")
    status=$(cat "$battery_path/status" 2>/dev/null || echo "Unknown")

    if [ "$status" == "Charging" ] || [ "$status" == "Full" ]; then
        return 0
    else
        return 1
    fi
}

is_on_ac() {
    # Check AC adapters
    for adapter in "$POWER_SUPPLY_DIR"/AC*/online; do
        if [ -f "$adapter" ] && [ "$(cat "$adapter" 2>/dev/null)" == "1" ]; then
            return 0
        fi
    done

    # Also check ADP* devices
    for adapter in "$POWER_SUPPLY_DIR"/ADP*/online; do
        if [ -f "$adapter" ] && [ "$(cat "$adapter" 2>/dev/null)" == "1" ]; then
            return 0
        fi
    done

    return 1
}

# --- Charging Threshold Functions ---

get_charge_thresholds() {
    local battery_name
    battery_name=$(find_battery_device 2>/dev/null || echo "$BATTERY_NAME")

    if ! is_battery_present "$battery_name"; then
        log_error "No battery found."
        return 1
    fi

    local battery_path
    battery_path=$(get_battery_path "$battery_name")

    log_info "Charging Thresholds:"
    echo "==================================="

    local start_threshold stop_threshold
    start_threshold=$(cat "$battery_path/charge_start_threshold" 2>/dev/null || echo "N/A")
    stop_threshold=$(cat "$battery_path/charge_stop_threshold" 2>/dev/null || echo "N/A")

    if [ "$start_threshold" == "N/A" ] && [ "$stop_threshold" == "N/A" ]; then
        log_warn "Charging thresholds are not supported by this hardware."
        log_info "ThinkPad and some Dell laptops support this feature."
        return 1
    fi

    echo "Start: $start_threshold%"
    echo "Stop:  $stop_threshold%"
    echo "==================================="
}

set_charge_start_threshold() {
    local threshold="$1"

    if ! [[ "$threshold" =~ ^[0-9]+$ ]] || [ "$threshold" -lt 0 ] || [ "$threshold" -gt 100 ]; then
        log_error "Threshold must be a number between 0 and 100."
        return 1
    fi

    local battery_name
    battery_name=$(find_battery_device 2>/dev/null || echo "$BATTERY_NAME")
    local battery_path
    battery_path=$(get_battery_path "$battery_name")

    local threshold_file="$battery_path/charge_start_threshold"

    if [ ! -f "$threshold_file" ]; then
        log_error "Charge start threshold not supported by this hardware."
        return 1
    fi

    log_info "Setting charge start threshold to: $threshold%"

    if ! echo "$threshold" > "$threshold_file" 2>/dev/null; then
        log_error "Failed to set threshold. Permission denied?"
        return 1
    fi

    log_success "Charge start threshold set to: $threshold%"
}

set_charge_stop_threshold() {
    local threshold="$1"

    if ! [[ "$threshold" =~ ^[0-9]+$ ]] || [ "$threshold" -lt 0 ] || [ "$threshold" -gt 100 ]; then
        log_error "Threshold must be a number between 0 and 100."
        return 1
    fi

    local battery_name
    battery_name=$(find_battery_device 2>/dev/null || echo "$BATTERY_NAME")
    local battery_path
    battery_path=$(get_battery_path "$battery_name")

    local threshold_file="$battery_path/charge_stop_threshold"

    if [ ! -f "$threshold_file" ]; then
        log_error "Charge stop threshold not supported by this hardware."
        return 1
    fi

    log_info "Setting charge stop threshold to: $threshold%"

    if ! echo "$threshold" > "$threshold_file" 2>/dev/null; then
        log_error "Failed to set threshold. Permission denied?"
        return 1
    fi

    log_success "Charge stop threshold set to: $threshold%"
}

# --- Monitoring Function ---

monitor_battery() {
    local interval="${1:-10}"

    if ! [[ "$interval" =~ ^[0-9]+$ ]] || [ "$interval" -lt 1 ]; then
        log_error "Interval must be a positive number (seconds)."
        return 1
    fi

    log_info "Monitoring battery (refresh every ${interval}s). Press Ctrl+C to stop."
    echo "==================================="

    while true; do
        clear
        echo "GTA VI OS Battery Monitor - $(date)"
        echo "==================================="
        show_status
        echo "==================================="
        sleep "$interval"
    done
}

# --- Calibration Function ---

calibration_guide() {
    log_info "Battery Calibration Guide:"
    echo "==================================="
    echo "Battery calibration helps the system accurately report"
    echo "battery capacity. Follow these steps:"
    echo ""
    echo "1. Charge your battery to 100% (until full)."
    echo "2. Keep the laptop plugged in for at least 2 hours."
    echo "3. Unplug the charger and use the laptop normally."
    echo "4. Let the battery discharge completely (until shutdown)."
    echo "5. Leave the laptop off for 3-5 hours."
    echo "6. Plug in the charger and charge to 100% without interruption."
    echo ""
    echo "Note: Perform calibration every 2-3 months for best results."
    echo "      Do NOT calibrate frequently as it adds wear cycles."
    echo "==================================="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Battery Manager

Usage: $0 <command> [options]

Status:
  status                     Show detailed battery status report
  health                     Show battery health and capacity info
  capacity                   Show battery percentage only
  charging                   Check if battery is charging (exit 0=yes, 1=no)
  on-ac                      Check if system is on AC power (exit 0=yes, 1=no)

Charging Thresholds:
  get-thresholds             Show current charging thresholds (if supported)
  set-start <percent>         Set charge start threshold (0-100)
  set-stop <percent>         Set charge stop threshold (0-100)

Utilities:
  monitor [interval]         Continuously monitor battery (default: 10s)
  calibration                Show battery calibration guide
  help                       Show this help message

Notes:
  - Charging thresholds are supported on ThinkPads and some Dell laptops.
  - Setting thresholds requires root privileges (use sudo).
  - Use 'monitor' to watch battery drain/charge in real-time.

Examples:
  $0 status
  $0 health
  $0 capacity
  $0 get-thresholds
  $0 set-stop 80
  $0 monitor 5
  $0 calibration
HELP
}

# --- Main ---

main() {
    check_battery_deps

    local command="${1:-help}"
    shift || true

    case "$command" in
        status|info)
            show_status
            ;;
        health)
            show_health
            ;;
        capacity|percent)
            get_capacity
            ;;
        charging|is-charging)
            if is_charging; then
                log_info "Battery is charging or full."
                exit 0
            else
                log_info "Battery is discharging."
                exit 1
            fi
            ;;
        on-ac|ac-power)
            if is_on_ac; then
                log_info "System is on AC power."
                exit 0
            else
                log_info "System is on battery power."
                exit 1
            fi
            ;;
        get-thresholds|thresholds)
            get_charge_thresholds
            ;;
        set-start|start-threshold)
            local threshold="${1:-}"
            if [ -z "$threshold" ]; then
                log_error "Threshold percentage required."
                exit 1
            fi
            set_charge_start_threshold "$threshold"
            ;;
        set-stop|stop-threshold)
            local threshold="${1:-}"
            if [ -z "$threshold" ]; then
                log_error "Threshold percentage required."
                exit 1
            fi
            set_charge_stop_threshold "$threshold"
            ;;
        monitor|watch)
            local interval="${1:-10}"
            monitor_battery "$interval"
            ;;
        calibration|calibrate)
            calibration_guide
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