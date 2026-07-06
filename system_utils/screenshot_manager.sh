#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Screenshot Manager
# Provides unified screenshot capture (full, window, region) with backend
# fallbacks (gnome-screenshot -> scrot -> import).
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
SCREENSHOT_DIR="${HOME}/Pictures/Screenshots"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="screenshot_${TIMESTAMP}.png"
FULL_PATH="${SCREENSHOT_DIR}/${FILENAME}"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Screenshot operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

ensure_screenshot_dir() {
    if [ ! -d "$SCREENSHOT_DIR" ]; then
        mkdir -p "$SCREENSHOT_DIR"
    fi
}

detect_backend() {
    if command -v gnome-screenshot > /dev/null 2>&1; then
        echo "gnome-screenshot"
    elif command -v scrot > /dev/null 2>&1; then
        echo "scrot"
    elif command -v import > /dev/null 2>&1; then
        echo "import"
    else
        echo "none"
    fi
}

# --- Capture Functions ---

capture_full() {
    local delay="${1:-0}"
    local backend
    backend=$(detect_backend)
    
    ensure_screenshot_dir
    
    log_info "Taking full screenshot in $delay seconds..."
    sleep "$delay"
    
    case "$backend" in
        "gnome-screenshot")
            gnome-screenshot -f "$FULL_PATH" > /dev/null 2>&1
            ;;
        "scrot")
            scrot "$FULL_PATH" > /dev/null 2>&1
            ;;
        "import")
            import -window root "$FULL_PATH" > /dev/null 2>&1
            ;;
        *)
            log_error "No screenshot backend found (gnome-screenshot, scrot, or import)."
            return 1
            ;;
    esac
    
    if [ -f "$FULL_PATH" ]; then
        log_success "Screenshot saved to: $FULL_PATH"
    else
        log_error "Failed to capture screenshot."
        return 1
    fi
}

capture_window() {
    local delay="${1:-0}"
    local backend
    backend=$(detect_backend)
    
    ensure_screenshot_dir
    
    log_info "Capturing active window in $delay seconds..."
    sleep "$delay"
    
    case "$backend" in
        "gnome-screenshot")
            gnome-screenshot -w -f "$FULL_PATH" > /dev/null 2>&1
            ;;
        "scrot")
            scrot -u "$FULL_PATH" > /dev/null 2>&1
            ;;
        "import")
            # `import` doesn't have a direct "active window" flag, requires xprop/wmctrl
            # Fallback to full screen if active window can't be determined easily
            log_warn "import backend does not support active window natively. Capturing full screen."
            import -window root "$FULL_PATH" > /dev/null 2>&1
            ;;
        *)
            log_error "No screenshot backend found."
            return 1
            ;;
    esac
    
    if [ -f "$FULL_PATH" ]; then
        log_success "Screenshot saved to: $FULL_PATH"
    else
        log_error "Failed to capture screenshot."
        return 1
    fi
}

capture_region() {
    local backend
    backend=$(detect_backend)
    
    ensure_screenshot_dir
    
    log_info "Select a region to capture..."
    
    case "$backend" in
        "gnome-screenshot")
            gnome-screenshot -a -f "$FULL_PATH" > /dev/null 2>&1
            ;;
        "scrot")
            scrot -s "$FULL_PATH" > /dev/null 2>&1
            ;;
        "import")
            import "$FULL_PATH" > /dev/null 2>&1
            ;;
        *)
            log_error "No screenshot backend found."
            return 1
            ;;
    esac
    
    if [ -f "$FULL_PATH" ]; then
        log_success "Screenshot saved to: $FULL_PATH"
    else
        log_error "Failed to capture screenshot (or selection cancelled)."
        return 1
    fi
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Screenshot Manager

Usage: $0 <command> [delay]

Commands:
  full [delay]           Capture the entire screen (optional delay in seconds)
  window [delay]         Capture the currently active window
  region                 Interactively select a screen region to capture
  help                   Show this help message

Notes:
  - Screenshots are saved to: $SCREENSHOT_DIR
  - Supported backends: gnome-screenshot, scrot, ImageMagick (import)

Examples:
  $0 full
  $0 full 5
  $0 window
  $0 region
HELP
}

# --- Main ---

main() {
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        full|screen)
            local delay="${1:-0}"
            capture_full "$delay"
            ;;
        window|active)
            local delay="${1:-0}"
            capture_window "$delay"
            ;;
        region|select)
            capture_region
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