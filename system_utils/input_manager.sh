#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Input Manager
# Manages input devices (keyboards, mice, touchpads) via xinput and xset.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Configuration ---
XINPUT_CMD="xinput"
XSET_CMD="xset"
SETXKBMAP_CMD="setxkbmap"
CONFIG_DIR="${HOME}/.config/vice-os"
INPUT_STATE="${CONFIG_DIR}/input.state"

# --- Helper Functions ---

check_input_deps() {
    check_dependencies "xinput" "xset"

    if [ -z "${DISPLAY:-}" ]; then
        log_error "No DISPLAY environment variable set."
        exit 1
    fi
}

ensure_config_dir() {
    if [ ! -d "$CONFIG_DIR" ]; then
        mkdir -p "$CONFIG_DIR"
    fi
}

# --- Listing Functions ---

list_devices() {
    log_info "Input Devices:"
    echo "==================================="

    "$XINPUT_CMD" list 2>/dev/null || true

    echo "==================================="
}

list_keyboards() {
    log_info "Keyboard Devices:"
    echo "==================================="

    "$XINPUT_CMD" list 2>/dev/null | grep -i "keyboard" || true
    echo "==================================="
}

list_mice() {
    log_info "Mouse Devices:"
    echo "==================================="

    "$XINPUT_CMD" list 2>/dev/null | grep -i "mouse" || true
    echo "==================================="
}

list_touchpads() {
    log_info "Touchpad Devices:"
    echo "==================================="

    "$XINPUT_CMD" list 2>/dev/null | grep -i "touchpad" || true
    echo "==================================="
}

# --- Device Info Functions ---

device_info() {
    local device_name="$1"

    if [ -z "$device_name" ]; then
        log_error "Device name required."
        return 1
    fi

    log_info "Device Information: $device_name"
    echo "==================================="
    "$XINPUT_CMD" list "$device_name" 2>/dev/null || true
    echo ""
    "$XINPUT_CMD" list-props "$device_name" 2>/dev/null || true
    echo "==================================="
}

# --- Enable/Disable Functions ---

enable_device() {
    local device_name="$1"

    if [ -z "$device_name" ]; then
        log_error "Device name required."
        return 1
    fi

    log_info "Enabling input device: $device_name"

    if "$XINPUT_CMD" enable "$device_name" 2>/dev/null; then
        log_success "Device '$device_name' enabled."
    else
        log_error "Failed to enable '$device_name'."
        return 1
    fi
}

disable_device() {
    local device_name="$1"

    if [ -z "$device_name" ]; then
        log_error "Device name required."
        return 1
    fi

    log_info "Disabling input device: $device_name"

    if "$XINPUT_CMD" disable "$device_name" 2>/dev/null; then
        log_success "Device '$device_name' disabled."
    else
        log_error "Failed to disable '$device_name'."
        return 1
    fi
}

toggle_touchpad() {
    log_info "Toggling touchpad..."

    # Find touchpad device name
    local touchpad_name
    touchpad_name=$("$XINPUT_CMD" list 2>/dev/null | grep -i "touchpad" | head -n 1 | sed 's/.*id=\([0-9]*\).*/\1/')

    if [ -z "$touchpad_name" ]; then
        log_error "No touchpad found."
        return 1
    fi

    # Check current state
    local current_state
    current_state=$("$XINPUT_CMD" list-props "$touchpad_name" 2>/dev/null | grep "Device Enabled" | awk '{print $NF}')

    if [ "$current_state" == "1" ]; then
        disable_device "$touchpad_name"
    else
        enable_device "$touchpad_name"
    fi
}

# --- Keyboard Configuration Functions ---

set_keyboard_layout() {
    local layout="$1"
    local variant="${2:-}"

    if [ -z "$layout" ]; then
        log_error "Layout required (e.g., us, de, fr)."
        return 1
    fi

    if ! command -v "$SETXKBMAP_CMD" > /dev/null 2>&1; then
        log_error "setxkbmap not found. Install 'x11-xkb-utils'."
        return 1
    fi

    log_info "Setting keyboard layout: $layout"

    if [ -n "$variant" ]; then
        "$SETXKBMAP_CMD" -layout "$layout" -variant "$variant"
    else
        "$SETXKBMAP_CMD" -layout "$layout"
    fi

    log_success "Keyboard layout set to: $layout"
    if [ -n "$variant" ]; then
        log_info "Variant: $variant"
    fi
}

set_repeat_rate() {
    local delay="${1:-250}"
    local rate="${2:-25}"

    if ! [[ "$delay" =~ ^[0-9]+$ ]]; then
        log_error "Delay must be a number (milliseconds)."
        return 1
    fi

    if ! [[ "$rate" =~ ^[0-9]+$ ]]; then
        log_error "Rate must be a number (keys per second)."
        return 1
    fi

    log_info "Setting keyboard repeat rate: delay=${delay}ms rate=${rate}/s"

    "$XSET_CMD" r rate "$delay" "$rate"

    log_success "Repeat rate set. Delay: ${delay}ms, Rate: ${rate}/s"
}

show_repeat_rate() {
    log_info "Current Keyboard Settings:"
    echo "==================================="

    # xset q shows the current settings
    "$XSET_CMD" q 2>/dev/null | grep -A 5 "auto repeat"
    echo "==================================="
}

# --- Mouse Configuration Functions ---

set_mouse_accel() {
    local acceleration="${1:-1.0}"
    local threshold="${2:-0}"

    log_info "Setting mouse acceleration: $acceleration (threshold: $threshold)"

    "$XSET_CMD" m "$acceleration" "$threshold"
    log_success "Mouse acceleration set."
}

show_mouse_settings() {
    log_info "Current Mouse Settings:"
    echo "==================================="

    "$XSET_CMD" q 2>/dev/null | grep -A 5 "Pointer"
    echo "==================================="
}

# --- Persistence Functions ---

save_settings() {
    local profile_name="${1:-default}"

    ensure_config_dir

    local state_file="${INPUT_STATE}.${profile_name}"

    log_info "Saving input settings as profile: $profile_name"

    # Save xset settings
    {
        echo "# Vice OS Input Settings - $profile_name ($(date))"
        echo "# Generated by input_manager.sh"
        echo ""

        # Extract repeat rate from xset q
        local delay rate
        delay=$("$XSET_CMD" q 2>/dev/null | grep "auto repeat" | awk '{print $4}')
        rate=$("$XSET_CMD" q 2>/dev/null | grep "auto repeat" | awk '{print $6}')
        echo "# Keyboard repeat rate"
        echo "xset r rate $delay $rate"
        echo ""
        echo "# Mouse acceleration"
        "$XSET_CMD" q 2>/dev/null | grep "acceleration:" | sed 's/.*acceleration:\s*/xset m /' >> "$state_file"
        echo ""
        echo "# Keyboard layout"
        "$SETXKBMAP_CMD" -query 2>/dev/null | grep "layout:" | sed 's/layout:/setxkbmap -layout/' >> "$state_file"
    } > "$state_file"

    log_success "Input settings saved to: $state_file"
}

load_settings() {
    local profile_name="${1:-default}"

    local state_file="${INPUT_STATE}.${profile_name}"

    if [ ! -f "$state_file" ]; then
        log_error "Settings profile '$profile_name' not found."
        return 1
    fi

    log_info "Loading input settings: $profile_name"

    while IFS= read -r line; do
        # Skip comments and empty lines
        if [[ "$line" =~ ^# ]] || [[ -z "$line" ]]; then
            continue
        fi

        # Validate the line: only allow xset/setxkbmap commands from trusted config
        if [[ "$line" =~ ^(xset|setxkbmap)\ [a-zA-Z0-9._\ -]+$ ]]; then
            log_info "Applying: $line"
            $line 2>/dev/null || true
        else
            log_warn "Skipping untrusted line: $line"
        fi
    done < "$state_file"

    log_success "Input settings loaded."
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Input Manager

Usage: $0 <command> [options]

Listing:
  list                        List all input devices
  keyboards                   List keyboard devices
  mice                        List mouse devices
  touchpads                   List touchpad devices

Enable/Disable:
  enable <device>             Enable an input device
  disable <device>            Disable an input device
  toggle-touchpad             Toggle touchpad on/off

Keyboard:
  set-layout <layout> [variant]  Set keyboard layout (e.g., us, de)
  set-repeat <delay> <rate>       Set repeat delay (ms) and rate (keys/s)
  show-repeat                     Show current repeat settings

Mouse:
  set-accel <accel> [threshold]   Set mouse acceleration and threshold
  show-mouse                      Show current mouse settings

Persistence:
  save [name]                     Save current settings as a profile
  load [name]                     Load a saved settings profile

Information:
  info <device>                   Show detailed device info and properties

Help:
  help                            Show this help message

Notes:
  - Device names can be found using 'list' command.
  - Some operations require root (use sudo).
  - Settings are saved to: $CONFIG_DIR

Examples:
  $0 list
  $0 toggle-touchpad
  $0 set-layout us
  $0 set-repeat 250 30
  $0 set-accel 2.0 5
  $0 save laptop
  $0 load laptop
HELP
}

# --- Main ---

main() {
    local command="${1:-help}"
    if [ "$command" = "help" ] || [ "$command" = "--help" ] || [ "$command" = "-h" ]; then
        show_help
        exit 0
    fi
    shift || true

    check_input_deps

    case "$command" in
        list|ls|devices)
            list_devices
            ;;
        keyboards|keyboard)
            list_keyboards
            ;;
        mice|mouse)
            list_mice
            ;;
        touchpads|touchpad)
            list_touchpads
            ;;
        info|show)
            local device="${1:-}"
            if [ -z "$device" ]; then
                log_error "Device name required."
                exit 1
            fi
            device_info "$device"
            ;;
        enable)
            local device="${1:-}"
            if [ -z "$device" ]; then
                log_error "Device name required."
                exit 1
            fi
            enable_device "$device"
            ;;
        disable)
            local device="${1:-}"
            if [ -z "$device" ]; then
                log_error "Device name required."
                exit 1
            fi
            disable_device "$device"
            ;;
        toggle-touchpad|touchpad-toggle)
            toggle_touchpad
            ;;
        set-layout|layout)
            local layout="${1:-}"
            if [ -z "$layout" ]; then
                log_error "Layout required."
                exit 1
            fi
            local variant="${2:-}"
            set_keyboard_layout "$layout" "$variant"
            ;;
        set-repeat|repeat)
            local delay="${1:-250}"
            local rate="${2:-25}"
            set_repeat_rate "$delay" "$rate"
            ;;
        show-repeat|repeat-info)
            show_repeat_rate
            ;;
        set-accel|accel)
            local accel="${1:-1.0}"
            local threshold="${2:-0}"
            set_mouse_accel "$accel" "$threshold"
            ;;
        show-mouse|mouse-info)
            show_mouse_settings
            ;;
        save)
            local name="${1:-default}"
            save_settings "$name"
            ;;
        load)
            local name="${1:-default}"
            load_settings "$name"
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