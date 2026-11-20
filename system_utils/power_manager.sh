#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Power Manager
# Provides suspend, hibernate, hybrid-sleep, power profile switching,
# and battery status reporting for desktop and laptop systems.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Configuration ---
POWER_PROFILES_DIR="/sys/firmware/acpi/platform_profile"
CPU_GOVERNOR_DIR="/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"
BATTERY_PATH="/sys/class/power_supply/BAT0"
UPOWER_CMD="upower"
SYSTEMCTL_CMD="systemctl"

# --- Helper Functions ---

check_power_dependencies() {
    check_dependencies "systemctl"

    # Check for upower (optional, for battery reporting)
    if ! command -v "$UPOWER_CMD" > /dev/null 2>&1; then
        log_warn "upower not found. Battery status features will be limited."
    fi
}

check_battery_present() {
    if [ ! -d "$BATTERY_PATH" ]; then
        log_error "No battery found at $BATTERY_PATH."
        log_info "This system may not have a battery (desktop or VM)."
        return 1
    fi
    return 0
}

# --- Power State Functions ---

do_suspend() {
    log_info "Suspending system to RAM..."
    if ! "$SYSTEMCTL_CMD" suspend; then
        log_error "Failed to suspend system."
        return 1
    fi
    log_success "System suspended successfully."
}

do_hibernate() {
    log_info "Hibernating system to disk..."

    # Check if swap space is available for hibernation
    if ! swapon --show | grep -q "swap"; then
        log_error "No swap space detected. Hibernation requires swap space."
        log_info "Tip: Vice OS uses ZRAM, which does not support hibernation."
        log_info "Consider adding a disk swap partition for hibernation support."
        return 1
    fi

    if ! "$SYSTEMCTL_CMD" hibernate; then
        log_error "Failed to hibernate system."
        return 1
    fi
    log_success "System hibernated successfully."
}

do_hybrid_sleep() {
    log_info "Entering hybrid sleep (suspend + hibernate)..."

    if ! swapon --show | grep -q "swap"; then
        log_warn "No swap space for hibernation fallback. Falling back to suspend only."
        do_suspend
        return $?
    fi

    if ! "$SYSTEMCTL_CMD" hybrid-sleep; then
        log_error "Failed to enter hybrid sleep."
        return 1
    fi
    log_success "Hybrid sleep entered successfully."
}

do_suspend_then_hibernate() {
    log_info "Entering suspend-then-hibernate mode..."

    if ! swapon --show | grep -q "swap"; then
        log_warn "No swap space for hibernation. Falling back to suspend only."
        do_suspend
        return $?
    fi

    if ! "$SYSTEMCTL_CMD" suspend-then-hibernate; then
        log_error "Failed to enter suspend-then-hibernate."
        return 1
    fi
    log_success "Suspend-then-hibernate entered successfully."
}

# --- Power Profile Functions ---

set_power_profile() {
    local profile="$1"

    case "$profile" in
        performance|balanced|power-saver)
            ;;
        *)
            log_error "Invalid power profile: $profile"
            log_info "Valid profiles: performance, balanced, power-saver"
            return 1
            ;;
    esac

    # Try ACPI platform profile first (modern laptops)
    if [ -f "$POWER_PROFILES_DIR" ]; then
        log_info "Setting ACPI platform profile to: $profile"
        if ! echo "$profile" > "$POWER_PROFILES_DIR" 2>/dev/null; then
            log_warn "Failed to set ACPI platform profile. Trying CPU governor fallback."
        else
            log_success "ACPI platform profile set to: $profile"
            return 0
        fi
    fi

    # Fallback: Set CPU governor manually
    local governor
    case "$profile" in
        performance)
            governor="performance"
            ;;
        balanced)
            governor="schedutil"
            ;;
        power-saver)
            governor="powersave"
            ;;
    esac

    if [ -f "$CPU_GOVERNOR_DIR" ]; then
        log_info "Setting CPU governor to: $governor"
        for cpu_dir in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
            if [ -f "$cpu_dir" ]; then
                echo "$governor" > "$cpu_dir" 2>/dev/null || true
            fi
        done
        log_success "CPU governor set to: $governor"
    else
        log_error "Cannot set power profile. Neither ACPI platform profile nor CPU governor is available."
        return 1
    fi
}

get_power_profile() {
    if [ -f "$POWER_PROFILES_DIR" ]; then
        cat "$POWER_PROFILES_DIR" 2>/dev/null || echo "unknown"
    elif [ -f "$CPU_GOVERNOR_DIR" ]; then
        local gov
        gov=$(cat "$CPU_GOVERNOR_DIR" 2>/dev/null || echo "unknown")
        case "$gov" in
            performance) echo "performance" ;;
            schedutil|ondemand) echo "balanced" ;;
            powersave) echo "power-saver" ;;
            *) echo "unknown" ;;
        esac
    else
        echo "unknown"
    fi
}

# --- Battery Status Functions ---

get_battery_status() {
    if ! check_battery_present; then
        return 1
    fi

    local status capacity rate time_to_empty time_to_full
    status=$(cat "$BATTERY_PATH/status" 2>/dev/null || echo "Unknown")
    capacity=$(cat "$BATTERY_PATH/capacity" 2>/dev/null || echo "N/A")

    echo "==================================="
    echo "     Battery Status Report"
    echo "==================================="
    echo "Status:       $status"
    echo "Capacity:     $capacity%"

    # Try upower for detailed info
    if command -v "$UPOWER_CMD" > /dev/null 2>&1; then
        local upower_info
        upower_info=$("$UPOWER_CMD" -i "$("$UPOWER_CMD" -e | grep BAT)" 2>/dev/null || true)

        if [ -n "$upower_info" ]; then
            local energy_rate
            energy_rate=$(echo "$upower_info" | grep "energy-rate" | awk '{print $2}')
            if [ -n "$energy_rate" ]; then
                echo "Discharge:    ${energy_rate} W"
            fi

            local time_empty
            time_empty=$(echo "$upower_info" | grep "time to empty" | sed 's/.*: *//')
            if [ -n "$time_empty" ]; then
                echo "Time to empty: $time_empty"
            fi
        fi
    fi

    echo "==================================="
}

get_battery_percentage() {
    if ! check_battery_present; then
        echo "N/A"
        return 1
    fi
    cat "$BATTERY_PATH/capacity" 2>/dev/null || echo "N/A"
}

is_on_ac_power() {
    local adapter
    for adapter in /sys/class/power_supply/AC*/online; do
        if [ -f "$adapter" ]; then
            if [ "$(cat "$adapter" 2>/dev/null)" == "1" ]; then
                return 0
            fi
        fi
    done
    return 1
}

# --- Screen Brightness Functions ---

get_brightness() {
    local backlight_dir="/sys/class/backlight"
    local device

    if [ ! -d "$backlight_dir" ]; then
        log_error "No backlight device found."
        return 1
    fi

    for device in "$backlight_dir"/*/; do
        if [ -f "${device}brightness" ] && [ -f "${device}max_brightness" ]; then
            local current max percentage
            current=$(cat "${device}brightness")
            max=$(cat "${device}max_brightness")
            if [ "$max" -gt 0 ]; then
                percentage=$((current * 100 / max))
                echo "$percentage"
                return 0
            fi
        fi
    done

    log_error "Could not read brightness level."
    return 1
}

set_brightness() {
    local level="$1"

    if ! [[ "$level" =~ ^[0-9]+$ ]] || [ "$level" -lt 0 ] || [ "$level" -gt 100 ]; then
        log_error "Brightness must be a number between 0 and 100."
        return 1
    fi

    local backlight_dir="/sys/class/backlight"

    if [ ! -d "$backlight_dir" ]; then
        log_error "No backlight device found."
        return 1
    fi

    for device in "$backlight_dir"/*/; do
        if [ -f "${device}brightness" ] && [ -f "${device}max_brightness" ]; then
            local max current
            max=$(cat "${device}max_brightness")
            local target=$((max * level / 100))

            # Try writing directly first
            if ! echo "$target" > "${device}brightness" 2>/dev/null; then
                # Fallback to xbacklight
                if command -v xbacklight > /dev/null 2>&1; then
                    xbacklight -set "$level"
                else
                    log_error "Permission denied. Try running with sudo or install xbacklight."
                    return 1
                fi
            fi

            log_success "Brightness set to: $level%"
            return 0
        fi
    done

    log_error "Could not set brightness."
    return 1
}

# --- Lid Action Configuration ---

set_lid_action() {
    local action="$1"

    case "$action" in
        suspend|hibernate|ignore|poweroff)
            ;;
        *)
            log_error "Invalid lid action: $action"
            log_info "Valid actions: suspend, hibernate, ignore, poweroff"
            return 1
            ;;
    esac

    local handle_file="/etc/systemd/logind.conf"
    local tmp_file

    tmp_file=$(mktemp)

    if [ ! -f "$handle_file" ]; then
        log_error "logind.conf not found at $handle_file"
        return 1
    fi

    # Update HandleLidSwitch setting
    sed "s/^#*HandleLidSwitch=.*/HandleLidSwitch=$action/" "$handle_file" > "$tmp_file"

    if ! cp "$tmp_file" "$handle_file"; then
        log_error "Failed to update logind configuration."
        rm -f "$tmp_file"
        return 1
    fi

    rm -f "$tmp_file"

    # Reload systemd-logind
    if ! "$SYSTEMCTL_CMD" restart systemd-logind 2>/dev/null; then
        log_warn "Could not restart systemd-logind. Changes will take effect on next boot."
    fi

    log_success "Lid action set to: $action"
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Power Manager

Usage: $0 <command> [options]

Commands:
  suspend                  Suspend system to RAM
  hibernate                Hibernate system to disk (requires swap)
  hybrid-sleep             Suspend + hibernate simultaneously
  suspend-then-hibernate   Suspend, then hibernate after delay

Power Profiles:
  set-profile <profile>    Set power profile (performance|balanced|power-saver)
  get-profile              Get current power profile

Battery:
  battery-status           Show detailed battery information
  battery-percent          Show battery percentage only
  on-ac                    Check if system is on AC power (exit 0=yes, 1=no)

Brightness:
  get-brightness           Get current screen brightness (0-100)
  set-brightness <level>   Set screen brightness (0-100)

Lid Action:
  set-lid-action <action>  Set lid switch action (suspend|hibernate|ignore|poweroff)

Help:
  help                     Show this help message

Examples:
  $0 suspend
  $0 set-profile performance
  $0 set-brightness 50
  $0 battery-status
HELP
}

# --- Main ---

main() {
    check_root

    local command="${1:-help}"
    shift || true

    case "$command" in
        suspend)
            do_suspend
            ;;
        hibernate)
            do_hibernate
            ;;
        hybrid-sleep)
            do_hybrid_sleep
            ;;
        suspend-then-hibernate)
            do_suspend_then_hibernate
            ;;
        set-profile)
            local profile="${1:-}"
            if [ -z "$profile" ]; then
                log_error "Power profile not specified."
                log_info "Valid profiles: performance, balanced, power-saver"
                exit 1
            fi
            set_power_profile "$profile"
            ;;
        get-profile)
            echo "$(get_power_profile)"
            ;;
        battery-status)
            get_battery_status
            ;;
        battery-percent)
            get_battery_percentage
            ;;
        on-ac)
            if is_on_ac_power; then
                log_info "System is on AC power."
                exit 0
            else
                log_info "System is on battery power."
                exit 1
            fi
            ;;
        get-brightness)
            get_brightness
            ;;
        set-brightness)
            local level="${1:-}"
            if [ -z "$level" ]; then
                log_error "Brightness level not specified."
                log_info "Usage: $0 set-brightness <0-100>"
                exit 1
            fi
            set_brightness "$level"
            ;;
        set-lid-action)
            local action="${1:-}"
            if [ -z "$action" ]; then
                log_error "Lid action not specified."
                log_info "Valid actions: suspend, hibernate, ignore, poweroff"
                exit 1
            fi
            set_lid_action "$action"
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