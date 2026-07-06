#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Panel Manager
# Manages custom TopBar panel settings for the PyQt5 desktop shell.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
CONFIG_DIR="${HOME}/.config/vice-os"
PANEL_FILE="${CONFIG_DIR}/panel.conf"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Panel operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

ensure_config_dir() {
    if [ ! -d "$CONFIG_DIR" ]; then
        mkdir -p "$CONFIG_DIR"
    fi
}

get_setting() {
    local key="$1"
    if [ ! -f "$PANEL_FILE" ]; then
        echo ""
        return 0
    fi
    grep "^${key}=" "$PANEL_FILE" | cut -d= -f2-
}

set_setting() {
    local key="$1"
    local value="$2"
    
    ensure_config_dir
    
    # If file doesn't exist, just write the setting
    if [ ! -f "$PANEL_FILE" ]; then
        echo "${key}=${value}" > "$PANEL_FILE"
        return 0
    fi
    
    # If key exists, replace it; otherwise, append it
    if grep -q "^${key}=" "$PANEL_FILE"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$PANEL_FILE"
    else
        echo "${key}=${value}" >> "$PANEL_FILE"
    fi
}

# --- View Functions ---

show_settings() {
    log_info "Current Panel Settings:"
    echo "==================================="
    
    if [ ! -f "$PANEL_FILE" ]; then
        log_info "No panel configuration found. Using defaults."
        return 0
    fi
    
    cat "$PANEL_FILE"
    echo "==================================="
}

# --- Set Functions ---

set_clock_format() {
    local format="$1"
    
    case "$format" in
        12h|24h)
            ;;
        *)
            log_error "Invalid clock format: $format (use 12h or 24h)"
            return 1
            ;;
    esac
    
    local strftime_format="%H:%M:%S"
    if [ "$format" == "12h" ]; then
        strftime_format="%I:%M:%S %p"
    fi
    
    log_info "Setting clock format to: $format ($strftime_format)"
    set_setting "clock_format" "$strftime_format"
    log_success "Clock format updated. Restart shell to apply."
}

set_position() {
    local position="$1"
    
    case "$position" in
        top|bottom)
            ;;
        *)
            log_error "Invalid position: $position (use top or bottom)"
            return 1
            ;;
    esac
    
    log_info "Setting panel position to: $position"
    set_setting "position" "$position"
    log_success "Position updated. Restart shell to apply."
}

toggle_widget() {
    local widget="$1"
    local enabled="${2:-true}"
    
    case "$widget" in
        cpu|ram|clock|exit)
            ;;
        *)
            log_error "Invalid widget name: $widget (valid: cpu, ram, clock, exit)"
            return 1
            ;;
    esac
    
    case "$enabled" in
        true|false)
            ;;
        *)
            log_error "Enabled must be true or false"
            return 1
            ;;
    esac
    
    log_info "Setting widget '$widget' visibility to: $enabled"
    set_setting "show_${widget}" "$enabled"
    log_success "Widget visibility updated. Restart shell to apply."
}

set_height() {
    local height="$1"
    
    if ! [[ "$height" =~ ^[0-9]+$ ]] || [ "$height" -lt 20 ] || [ "$height" -gt 60 ]; then
        log_error "Height must be a number between 20 and 60."
        return 1
    fi
    
    log_info "Setting panel height to: $height"
    set_setting "height" "$height"
    log_success "Height updated. Restart shell to apply."
}

# --- Reset Function ---

reset_panel() {
    log_warn "Resetting panel to default configuration."
    rm -f "$PANEL_FILE"
    
    ensure_config_dir
    cat <<DEFAULTS > "$PANEL_FILE"
position=top
height=30
clock_format=%H:%M:%S
show_cpu=true
show_ram=true
show_clock=true
show_exit=true
DEFAULTS
    
    log_success "Panel reset to defaults."
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Panel Manager

Usage: $0 <command> [options]

Commands:
  show                         Show current panel settings
  set-clock <12h|24h>         Set clock format
  set-position <top|bottom>   Set panel position
  set-height <pixels>         Set panel height (20-60)
  toggle <widget> <true|false>  Toggle widget visibility (cpu, ram, clock, exit)
  reset                        Reset panel to default settings
  help                         Show this help message

Notes:
  - Configuration is stored in: $PANEL_FILE
  - Changes require a restart of the desktop shell (vice_shell.py) to take effect.

Examples:
  $0 show
  $0 set-clock 12h
  $0 set-position bottom
  $0 set-height 40
  $0 toggle cpu false
  $0 reset
HELP
}

# --- Main ---

main() {
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        show|status)
            show_settings
            ;;
        set-clock|clock)
            local format="${1:-}"
            if [ -z "$format" ]; then
                log_error "Format required (12h or 24h)."
                exit 1
            fi
            set_clock_format "$format"
            ;;
        set-position|position)
            local position="${1:-}"
            if [ -z "$position" ]; then
                log_error "Position required (top or bottom)."
                exit 1
            fi
            set_position "$position"
            ;;
        set-height|height)
            local height="${1:-}"
            if [ -z "$height" ]; then
                log_error "Height required."
                exit 1
            fi
            set_height "$height"
            ;;
        toggle|widget)
            local widget="${1:-}"
            local enabled="${2:-true}"
            if [ -z "$widget" ]; then
                log_error "Widget name required."
                exit 1
            fi
            toggle_widget "$widget" "$enabled"
            ;;
        reset|defaults)
            reset_panel
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