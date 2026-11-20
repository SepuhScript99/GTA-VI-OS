#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Wallpaper Manager
# Manages desktop wallpaper setting, listing, and randomization.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Configuration ---
WALLPAPER_DIR="/usr/share/backgrounds"
CONFIG_DIR="${HOME}/.config/vice-os"
STATE_FILE="${CONFIG_DIR}/wallpaper.state"
FEH_CMD="feh"

# --- Helper Functions ---

check_wallpaper_deps() {
    if [[ "${VICE_TESTING:-0}" == "1" ]]; then
        return 0
    fi
    check_dependencies "feh"

    if [ -z "${DISPLAY:-}" ]; then
        log_error "No DISPLAY environment variable set. Cannot set wallpaper."
        exit 1
    fi
}

ensure_config_dir() {
    if [ ! -d "$CONFIG_DIR" ]; then
        mkdir -p "$CONFIG_DIR"
    fi
}

get_current_wallpaper() {
    if [ -f "$STATE_FILE" ]; then
        cat "$STATE_FILE"
    else
        echo ""
    fi
}

save_wallpaper_state() {
    local path="$1"
    ensure_config_dir
    echo "$path" > "$STATE_FILE"
}

# --- Core Functions ---

list_wallpapers() {
    log_info "Available Wallpapers:"
    echo "==================================="

    if [ ! -d "$WALLPAPER_DIR" ]; then
        log_error "Wallpaper directory $WALLPAPER_DIR does not exist."
        return 1
    fi

    local current
    current=$(get_current_wallpaper)

    local found=false
    for file in "$WALLPAPER_DIR"/*; do
        if [ -f "$file" ]; then
            local name
            name=$(basename "$file")

            if [ "$file" == "$current" ]; then
                echo "  [Active] $name"
            else
                echo "  [ ]      $name"
            fi
            found=true
        fi
    done

    if [ "$found" == false ]; then
        log_info "No wallpapers found in $WALLPAPER_DIR."
    fi

    echo "==================================="
}

set_wallpaper() {
    local image_path="$1"
    local mode="${2:-fill}"

    if [ -z "$image_path" ]; then
        log_error "Image path required."
        return 1
    fi

    # Resolve to absolute path
    if [[ "$image_path" != /* ]]; then
        # Check if it's a filename in the wallpaper dir
        if [ -f "${WALLPAPER_DIR}/${image_path}" ]; then
            image_path="${WALLPAPER_DIR}/${image_path}"
        else
            image_path="$(pwd)/${image_path}"
        fi
    fi

    if [ ! -f "$image_path" ]; then
        log_error "Image file not found: $image_path"
        return 1
    fi

    # Validate mode
    case "$mode" in
        fill|scale|center|max|tile)
            ;;
        *)
            log_error "Invalid mode: $mode (valid: fill, scale, center, max, tile)"
            return 1
            ;;
    esac

    log_info "Setting wallpaper: $(basename "$image_path") (mode: $mode)"

    # Map mode to feh flags
    local feh_mode
    case "$mode" in
        fill)   feh_mode="--bg-fill" ;;
        scale)  feh_mode="--bg-scale" ;;
        center) feh_mode="--bg-center" ;;
        max)    feh_mode="--bg-max" ;;
        tile)   feh_mode="--bg-tile" ;;
    esac

    if ! "$FEH_CMD" "$feh_mode" "$image_path" > /dev/null 2>&1; then
        log_error "Failed to set wallpaper."
        return 1
    fi

    save_wallpaper_state "$image_path"
    log_success "Wallpaper set successfully."
}

set_random_wallpaper() {
    local mode="${1:-fill}"

    log_info "Selecting random wallpaper..."

    if [ ! -d "$WALLPAPER_DIR" ]; then
        log_error "Wallpaper directory $WALLPAPER_DIR does not exist."
        return 1
    fi

    # Collect all image files
    local images=()
    for file in "$WALLPAPER_DIR"/*.{jpg,jpeg,png,bmp}; do
        if [ -f "$file" ]; then
            images+=("$file")
        fi
    done

    if [ ${#images[@]} -eq 0 ]; then
        log_error "No image files found in $WALLPAPER_DIR."
        return 1
    fi

    # Pick a random one
    local random_index=$((RANDOM % ${#images[@]}))
    local random_image="${images[$random_index]}"

    set_wallpaper "$random_image" "$mode"
}

restore_wallpaper() {
    local current
    current=$(get_current_wallpaper)

    if [ -z "$current" ]; then
        log_info "No saved wallpaper state. Setting default..."
        set_wallpaper "${WALLPAPER_DIR}/vice_neon.jpg" "fill"
        return $?
    fi

    if [ ! -f "$current" ]; then
        log_warn "Saved wallpaper file no longer exists: $current"
        log_info "Setting default..."
        set_wallpaper "${WALLPAPER_DIR}/vice_neon.jpg" "fill"
        return $?
    fi

    log_info "Restoring wallpaper: $(basename "$current")"

    # We need to determine the mode used. For simplicity, default to fill on restore.
    if ! "$FEH_CMD" --bg-fill "$current" > /dev/null 2>&1; then
        log_error "Failed to restore wallpaper."
        return 1
    fi

    log_success "Wallpaper restored."
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Wallpaper Manager (Desktop Wallpaper)

Usage: $0 <command> [options]

Commands:
  list                        List available wallpapers
  set <path|name> [mode]     Set a specific wallpaper (mode: fill, scale, center, max, tile)
  random [mode]              Set a random wallpaper from the default directory
  restore                     Restore the last used wallpaper (used on login)
  current                     Show the current wallpaper path
  help                        Show this help message

Notes:
  - Wallpapers are stored in: $WALLPAPER_DIR
  - State is saved in: $STATE_FILE
  - If only a filename is provided for 'set', it is looked up in $WALLPAPER_DIR.

Examples:
  $0 list
  $0 set vice_neon.jpg fill
  $0 set /path/to/my/image.png center
  $0 random scale
  $0 restore
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

    check_wallpaper_deps

    case "$command" in
        list|ls)
            list_wallpapers
            ;;
        set|apply)
            local image="${1:-}"
            if [ -z "$image" ]; then
                log_error "Image path required."
                exit 1
            fi
            local mode="${2:-fill}"
            set_wallpaper "$image" "$mode"
            ;;
        random|rand)
            local mode="${1:-fill}"
            set_random_wallpaper "$mode"
            ;;
        restore|reload)
            restore_wallpaper
            ;;
        current|status)
            local current
            current=$(get_current_wallpaper)
            if [ -n "$current" ]; then
                echo "$current"
            else
                log_info "No wallpaper state saved."
            fi
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