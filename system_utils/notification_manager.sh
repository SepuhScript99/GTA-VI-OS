#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Notification Manager
# Provides a unified CLI for sending desktop notifications.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
NOTIFY_SEND_CMD="notify-send"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Notification operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_notification_deps() {
    if ! command -v "$NOTIFY_SEND_CMD" > /dev/null 2>&1; then
        log_error "notify-send not found. Install 'libnotify-bin'."
        exit 1
    fi
    
    if [ -z "${DISPLAY:-}" ]; then
        log_error "No DISPLAY environment variable set. Cannot send notification."
        log_info "This script must be run from an X session or with DISPLAY exported."
        exit 1
    fi
}

validate_urgency() {
    local urgency="$1"
    case "$urgency" in
        low|normal|critical)
            return 0
            ;;
        *)
            log_error "Invalid urgency level: $urgency"
            log_info "Valid levels: low, normal, critical"
            return 1
            ;;
    esac
}

# --- Core Functions ---

send_notification() {
    local title="$1"
    local body="${2:-}"
    local icon="${NOTIFY_ICON:-}"
    local urgency="${NOTIFY_URGENCY:-normal}"
    local timeout="${NOTIFY_TIMEOUT:-5000}" # Default 5 seconds
    
    if [ -z "$title" ]; then
        log_error "Notification title required."
        return 1
    fi
    
    validate_urgency "$urgency" || return 1
    
    local cmd_args=()
    cmd_args+=("--urgency" "$urgency")
    cmd_args+=("--expire-time" "$timeout")
    
    if [ -n "$icon" ]; then
        cmd_args+=("--icon" "$icon")
    fi
    
    cmd_args+=("$title")
    
    if [ -n "$body" ]; then
        cmd_args+=("$body")
    fi
    
    if ! "$NOTIFY_SEND_CMD" "${cmd_args[@]}"; then
        log_error "Failed to send notification."
        return 1
    fi
    
    log_success "Notification sent: $title"
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Notification Manager

Usage: $0 <title> [body] [options]

Arguments:
  title                     The title of the notification
  body                      The body text of the notification (optional)

Options:
  --icon <icon_name>        Specify an icon name or file path
  --urgency <level>         Set urgency level (low, normal, critical)
  --timeout <ms>            Set expiration time in milliseconds (default: 5000)

Help:
  help                      Show this help message

Notes:
  - Requires 'libnotify-bin' (notify-send) to be installed.
  - Requires an active X session (DISPLAY variable must be set).
  - Can be used in scripts to notify users of completion or errors.

Examples:
  $0 "Hello" "Welcome to Vice OS!"
  $0 "Update Complete" "System updated successfully." --icon system-software-update
  $0 "Battery Low" "Please plug in your charger." --urgency critical --timeout 10000
HELP
}

# --- Main ---

main() {
    check_notification_deps
    
    # If first argument is 'help', show help
    if [ "${1:-}" == "help" ] || [ "${1:-}" == "--help" ] || [ "${1:-}" == "-h" ]; then
        show_help
        exit 0
    fi
    
    local title="${1:-}"
    local body="${2:-}"
    
    if [ -z "$title" ]; then
        log_error "Title required."
        show_help
        exit 1
    fi
    
    shift 2 || true
    
    # Parse optional flags
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --icon)
                NOTIFY_ICON="${2:-}"
                shift 2
                ;;
            --urgency)
                NOTIFY_URGENCY="${2:-normal}"
                shift 2
                ;;
            --timeout)
                NOTIFY_TIMEOUT="${2:-5000}"
                shift 2
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    send_notification "$title" "$body"
}

main "$@"