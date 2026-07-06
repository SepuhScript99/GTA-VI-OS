#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Clipboard Manager
# Provides copy, paste, clear, and view functionality for the X11 clipboard.
# Supports automatic backend detection (xclip -> xsel).
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Clipboard operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_clipboard_deps() {
    if ! command -v xclip > /dev/null 2>&1 && ! command -v xsel > /dev/null 2>&1; then
        log_error "No clipboard utility found. Install 'xclip' or 'xsel'."
        exit 1
    fi
}

detect_backend() {
    if command -v xclip > /dev/null 2>&1; then
        echo "xclip"
    elif command -v xsel > /dev/null 2>&1; then
        echo "xsel"
    else
        echo "none"
    fi
}

# --- Copy Function ---

copy_to_clipboard() {
    local input
    local backend
    backend=$(detect_backend)
    
    # Read from argument or stdin
    if [ $# -gt 0 ]; then
        input="$*"
    else
        input=$(cat)
    fi
    
    if [ -z "$input" ]; then
        log_error "No input provided to copy."
        return 1
    fi
    
    case "$backend" in
        "xclip")
            echo -n "$input" | xclip -selection clipboard
            ;;
        "xsel")
            echo -n "$input" | xsel --clipboard --input
            ;;
        *)
            log_error "No clipboard backend available."
            return 1
            ;;
    esac
    
    log_success "Copied to clipboard: ${input:0:50}..."
}

# --- Paste Function ---

paste_from_clipboard() {
    local backend
    backend=$(detect_backend)
    
    case "$backend" in
        "xclip")
            xclip -selection clipboard -o
            ;;
        "xsel")
            xsel --clipboard --output
            ;;
        *)
            log_error "No clipboard backend available."
            return 1
            ;;
    esac
}

# --- View Function ---

show_clipboard() {
    log_info "Current Clipboard Content:"
    echo "==================================="
    paste_from_clipboard
    echo ""
    echo "==================================="
}

# --- Clear Function ---

clear_clipboard() {
    local backend
    backend=$(detect_backend)
    
    log_info "Clearing clipboard..."
    
    case "$backend" in
        "xclip")
            # Clear by writing empty string
            echo -n "" | xclip -selection clipboard
            ;;
        "xsel")
            xsel --clipboard --clear
            ;;
        *)
            log_error "No clipboard backend available."
            return 1
            ;;
    esac
    
    log_success "Clipboard cleared."
}

# --- Pipe Function ---

pipe_to_clipboard() {
    local backend
    backend=$(detect_backend)
    
    case "$backend" in
        "xclip")
            xclip -selection clipboard
            ;;
        "xsel")
            xsel --clipboard --input
            ;;
        *)
            log_error "No clipboard backend available."
            return 1
            ;;
    esac
    
    log_success "Data piped to clipboard."
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Clipboard Manager

Usage: $0 <command> [text]

Commands:
  copy <text>             Copy text to clipboard
  paste                   Paste clipboard content to stdout
  show                    Display current clipboard content
  clear                   Clear the clipboard (for security)
  pipe                    Pipe stdin to clipboard (e.g., 'cat file | $0 pipe')
  help                    Show this help message

Notes:
  - Supports both 'xclip' and 'xsel' backends automatically.
  - 'copy' without arguments reads from stdin.
  - 'clear' is useful for clearing sensitive data like passwords.

Examples:
  $0 copy "Hello, Vice OS!"
  $0 paste
  $0 show
  $0 clear
  echo "data" | $0 pipe
  $0 copy < /etc/hostname
HELP
}

# --- Main ---

main() {
    check_clipboard_deps
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        copy|set)
            if [ $# -gt 0 ]; then
                copy_to_clipboard "$@"
            else
                copy_to_clipboard
            fi
            ;;
        paste|get)
            paste_from_clipboard
            ;;
        show|view)
            show_clipboard
            ;;
        clear|wipe)
            clear_clipboard
            ;;
        pipe|stdin)
            pipe_to_clipboard
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