#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Shortcut Manager
# Provides creation, listing, and deletion of freedesktop.org .desktop entries.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
APP_DIR="${HOME}/.local/share/applications"
DESKTOP_DIR="${HOME}/Desktop"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Shortcut operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

ensure_dirs() {
    mkdir -p "$APP_DIR"
    mkdir -p "$DESKTOP_DIR"
}

validate_exec() {
    local exec_cmd="$1"
    
    # Extract the binary path (first word before space, ignore variables like %f)
    local binary
    binary=$(echo "$exec_cmd" | awk '{print $1}')
    
    # Remove quotes if present
    binary="${binary//\"/}"
    binary="${binary//\'/}"
    
    # Check if it's an absolute path or a command in PATH
    if [[ "$binary" == /* ]]; then
        if [ ! -x "$binary" ]; then
            log_warn "Binary '$binary' is not executable or does not exist."
        fi
    elif ! command -v "$binary" > /dev/null 2>&1; then
        log_warn "Command '$binary' not found in PATH."
    fi
}

sanitize_filename() {
    local name="$1"
    # Replace spaces and special characters with hyphens, lowercase
    echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd '[:alnum:]-'
}

# --- Create Function ---

create_shortcut() {
    local name="$1"
    local exec_cmd="$2"
    local icon="${3:-applications-other}"
    local terminal="${4:-false}"
    local categories="${5:-Utility;"
    local put_on_desktop="${6:-no}"
    
    if [ -z "$name" ] || [ -z "$exec_cmd" ]; then
        log_error "Name and Exec command are required."
        return 1
    fi
    
    ensure_dirs
    
    local filename
    filename=$(sanitize_filename "$name")
    local desktop_file="${APP_DIR}/${filename}.desktop"
    
    log_info "Creating shortcut: $name ($desktop_file)"
    
    validate_exec "$exec_cmd"
    
    # Write the .desktop file
    cat <<DESKTOP_FILE > "$desktop_file"
[Desktop Entry]
Version=1.0
Type=Application
Name=$name
Exec=$exec_cmd
Icon=$icon
Terminal=$terminal
Categories=$categories
DESKTOP_FILE
    
    chmod +x "$desktop_file"
    
    # Optionally copy to Desktop
    if [ "$put_on_desktop" == "yes" ] || [ "$put_on_desktop" == "--desktop" ]; then
        cp "$desktop_file" "${DESKTOP_DIR}/"
        chmod +x "${DESKTOP_DIR}/${filename}.desktop"
        log_info "Shortcut also placed on Desktop."
    fi
    
    log_success "Shortcut created successfully."
}

# --- List Function ---

list_shortcuts() {
    log_info "User Application Shortcuts:"
    echo "==================================="
    
    ensure_dirs
    
    local found=false
    for file in "$APP_DIR"/*.desktop; do
        if [ -f "$file" ]; then
            local name
            name=$(grep "^Name=" "$file" | cut -d= -f2-)
            local exec_cmd
            exec_cmd=$(grep "^Exec=" "$file" | cut -d= -f2-)
            printf "  %-30s %s\n" "$name" "$exec_cmd"
            found=true
        fi
    done
    
    if [ "$found" == false ]; then
        log_info "No user shortcuts found."
    fi
    
    echo "==================================="
}

# --- Remove Function ---

remove_shortcut() {
    local name="$1"
    
    if [ -z "$name" ]; then
        log_error "Shortcut name required."
        return 1
    fi
    
    local filename
    filename=$(sanitize_filename "$name")
    local desktop_file="${APP_DIR}/${filename}.desktop"
    local desktop_link="${DESKTOP_DIR}/${filename}.desktop"
    
    if [ ! -f "$desktop_file" ]; then
        log_error "Shortcut '$name' not found."
        log_info "Use '$0 list' to see available shortcuts."
        return 1
    fi
    
    log_info "Removing shortcut: $name"
    rm -f "$desktop_file" "$desktop_link"
    log_success "Shortcut removed."
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Shortcut Manager

Usage: $0 <command> [options]

Commands:
  create <name> <exec> [icon] [terminal] [categories] [--desktop]
                              Create a new application shortcut
  list                        List all user shortcuts
  remove <name>               Remove a shortcut by name
  help                        Show this help message

Create Options:
  name                        Display name of the application
  exec                        Command to execute (e.g., /usr/bin/firefox or xterm -e vim)
  icon                        Icon name or path (default: applications-other)
  terminal                    Run in terminal (true/false, default: false)
  categories                  Menu categories (default: Utility;)
  --desktop                   Also place the shortcut on the Desktop

Notes:
  - Shortcuts are stored in: $APP_DIR
  - Desktop shortcuts are stored in: $DESKTOP_DIR
  - Shortcut names are automatically sanitized for filenames.

Examples:
  $0 create "My Editor" "xterm -e vim" accessories-text-editor true Utility;Editor
  $0 create "Firefox" "firefox" firefox false Network;WebBrowser --desktop
  $0 list
  $0 remove "My Editor"
HELP
}

# --- Main ---

main() {
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        create|add)
            local name="${1:-}"
            local exec_cmd="${2:-}"
            if [ -z "$name" ] || [ -z "$exec_cmd" ]; then
                log_error "Name and Exec command required."
                log_info "Usage: $0 create <name> <exec> [icon] [terminal] [categories] [--desktop]"
                exit 1
            fi
            shift 2
            local icon="${1:-applications-other}"
            local terminal="${2:-false}"
            local categories="${3:-Utility;}"
            local desktop="no"
            
            # Check for --desktop flag in remaining args
            for arg in "$@"; do
                if [ "$arg" == "--desktop" ]; then
                    desktop="yes"
                fi
            done
            
            create_shortcut "$name" "$exec_cmd" "$icon" "$terminal" "$categories" "$desktop"
            ;;
        list|ls)
            list_shortcuts
            ;;
        remove|rm|delete)
            local name="${1:-}"
            if [ -z "$name" ]; then
                log_error "Shortcut name required."
                exit 1
            fi
            remove_shortcut "$name"
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