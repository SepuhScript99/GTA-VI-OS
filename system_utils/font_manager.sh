#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Font Manager
# Manages user-level font installation, removal, listing, and cache rebuilding.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Configuration ---
USER_FONT_DIR="${HOME}/.local/share/fonts"
FC_LIST_CMD="fc-list"
FC_CACHE_CMD="fc-cache"

# --- Helper Functions ---

check_font_deps() {
    check_dependencies "fc-list" "fc-cache"
}

ensure_font_dir() {
    if [ ! -d "$USER_FONT_DIR" ]; then
        mkdir -p "$USER_FONT_DIR"
    fi
}

# --- Core Functions ---

list_fonts() {
    log_info "Installed Fonts (Family names):"
    echo "==================================="

    # Use fc-list, extract family name, sort unique
    "$FC_LIST_CMD" : family | sort -u | while read -r family; do
        echo "  $family"
    done

    echo "==================================="
}

search_fonts() {
    local query="$1"

    if [ -z "$query" ]; then
        log_error "Search query required."
        return 1
    fi

    log_info "Searching fonts matching: '$query'"
    echo "==================================="

    local results
    results=$("$FC_LIST_CMD" | grep -i "$query")

    if [ -z "$results" ]; then
        log_info "No fonts found matching '$query'."
    else
        echo "$results"
    fi

    echo "==================================="
}

install_font() {
    local source_path="$1"

    if [ -z "$source_path" ]; then
        log_error "Font file path required."
        return 1
    fi

    # Resolve absolute path
    if [[ "$source_path" != /* ]]; then
        source_path="$(pwd)/${source_path}"
    fi

    if [ ! -f "$source_path" ]; then
        log_error "Font file not found: $source_path"
        return 1
    fi

    # Validate extension
    local ext="${source_path##*.}"
    ext=$(echo "$ext" | tr '[:upper:]' '[:lower:]')

    case "$ext" in
        ttf|otf|ttc)
            ;;
        *)
            log_error "Unsupported font format: .$ext (supported: .ttf, .otf, .ttc)"
            return 1
            ;;
    esac

    ensure_font_dir

    local filename
    filename=$(basename "$source_path")
    local dest_path="${USER_FONT_DIR}/${filename}"

    log_info "Installing font: $filename to $USER_FONT_DIR"

    cp "$source_path" "$dest_path"

    # Rebuild cache for the user directory
    log_info "Rebuilding font cache..."
    "$FC_CACHE_CMD" -f "$USER_FONT_DIR" > /dev/null 2>&1

    log_success "Font '$filename' installed successfully."
}

remove_font() {
    local font_name="$1"

    if [ -z "$font_name" ]; then
        log_error "Font filename required."
        return 1
    fi

    local font_path="${USER_FONT_DIR}/${font_name}"

    if [ ! -f "$font_path" ]; then
        log_error "Font '$font_name' not found in $USER_FONT_DIR."
        return 1
    fi

    log_info "Removing font: $font_name"
    rm -f "$font_path"

    log_info "Rebuilding font cache..."
    "$FC_CACHE_CMD" -f "$USER_FONT_DIR" > /dev/null 2>&1

    log_success "Font removed successfully."
}

rebuild_cache() {
    log_info "Rebuilding system font cache (this may take a moment)..."
    "$FC_CACHE_CMD" -f -v > /dev/null 2>&1
    log_success "Font cache rebuilt."
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Font Manager

Usage: $0 <command> [options]

Commands:
  list                      List all installed font families
  search <query>            Search installed fonts by name/path
  install <path>            Install a .ttf, .otf, or .ttc font file
  remove <filename>         Remove a font by filename from user directory
  rebuild-cache             Rebuild the system font cache
  help                      Show this help message

Notes:
  - User fonts are installed to: $USER_FONT_DIR
  - System-wide fonts require root privileges (use sudo apt install fonts-...)

Examples:
  $0 list
  $0 search "Mono"
  $0 install /path/to/MyCustomFont.ttf
  $0 remove MyCustomFont.ttf
  $0 rebuild-cache
HELP
}

# --- Main ---

main() {
    check_font_deps

    local command="${1:-help}"
    shift || true

    case "$command" in
        list|ls)
            list_fonts
            ;;
        search|find)
            local query="${1:-}"
            if [ -z "$query" ]; then
                log_error "Search query required."
                exit 1
            fi
            search_fonts "$query"
            ;;
        install|add)
            local path="${1:-}"
            if [ -z "$path" ]; then
                log_error "Font file path required."
                exit 1
            fi
            install_font "$path"
            ;;
        remove|rm)
            local name="${1:-}"
            if [ -z "$name" ]; then
                log_error "Font filename required."
                exit 1
            fi
            remove_font "$name"
            ;;
        rebuild-cache|cache)
            rebuild_cache
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