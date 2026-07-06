#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Dock Manager
# Manages custom application entries for the PyQt5 desktop dock.
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
DOCK_FILE="${CONFIG_DIR}/dock.conf"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Dock operation failed with exit code $exit_code."
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

# --- Add Function ---

add_dock_item() {
    local name="$1"
    local exec_cmd="$2"
    local icon="${3:-applications-other}"
    
    if [ -z "$name" ] || [ -z "$exec_cmd" ]; then
        log_error "Name and Exec command are required."
        return 1
    fi
    
    ensure_config_dir
    
    # Check if item already exists
    if [ -f "$DOCK_FILE" ] && grep -q "^${name}|" "$DOCK_FILE"; then
        log_warn "Dock item '$name' already exists."
        return 0
    fi
    
    log_info "Adding dock item: $name"
    echo "${name}|${exec_cmd}|${icon}" >> "$DOCK_FILE"
    
    log_success "Dock item '$name' added. Restart the desktop shell to apply."
}

# --- Remove Function ---

remove_dock_item() {
    local name="$1"
    
    if [ -z "$name" ]; then
        log_error "Item name required."
        return 1
    fi
    
    if [ ! -f "$DOCK_FILE" ]; then
        log_error "Dock configuration file not found."
        return 1
    fi
    
    if ! grep -q "^${name}|" "$DOCK_FILE"; then
        log_error "Dock item '$name' not found."
        return 1
    fi
    
    log_info "Removing dock item: $name"
    
    # Create a temp file without the matching line
    local tmp_file
    tmp_file=$(mktemp)
    grep -v "^${name}|" "$DOCK_FILE" > "$tmp_file"
    mv "$tmp_file" "$DOCK_FILE"
    
    log_success "Dock item '$name' removed. Restart the desktop shell to apply."
}

# --- List Function ---

list_dock_items() {
    log_info "Current Dock Items:"
    echo "==================================="
    
    if [ ! -f "$DOCK_FILE" ]; then
        log_info "No dock items configured."
        return 0
    fi
    
    while IFS='|' read -r name exec_cmd icon; do
        printf "  %-20s %-30s %s\n" "$name" "$exec_cmd" "$icon"
    done < "$DOCK_FILE"
    
    echo "==================================="
}

# --- Reset Function ---

reset_dock() {
    log_warn "Resetting dock to default configuration."
    rm -f "$DOCK_FILE"
    
    # Write default items
    ensure_config_dir
    cat <<DEFAULTS > "$DOCK_FILE"
Terminal|xterm|utilities-terminal
Browser|firefox|web-browser
Files|thunar|system-file-manager
Editor|geany|accessories-text-editor
DEFAULTS
    
    log_success "Dock reset to defaults."
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Dock Manager

Usage: $0 <command> [options]

Commands:
  add <name> <exec> [icon]    Add a new application to the dock
  remove <name>               Remove an application from the dock
  list                        List all dock items
  reset                       Reset dock to default items
  help                        Show this help message

Notes:
  - Configuration is stored in: $DOCK_FILE
  - Changes require a restart of the desktop shell (vice_shell.py) to take effect.

Examples:
  $0 add "Terminal" "xterm" "utilities-terminal"
  $0 add "Code" "code" "code"
  $0 remove "Code"
  $0 list
HELP
}

# --- Main ---

main() {
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        add)
            local name="${1:-}"
            local exec_cmd="${2:-}"
            if [ -z "$name" ] || [ -z "$exec_cmd" ]; then
                log_error "Name and Exec command required."
                exit 1
            fi
            local icon="${3:-applications-other}"
            add_dock_item "$name" "$exec_cmd" "$icon"
            ;;
        remove|rm)
            local name="${1:-}"
            if [ -z "$name" ]; then
                log_error "Item name required."
                exit 1
            fi
            remove_dock_item "$name"
            ;;
        list|ls)
            list_dock_items
            ;;
        reset|defaults)
            reset_dock
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