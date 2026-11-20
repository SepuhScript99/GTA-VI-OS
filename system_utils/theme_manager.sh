#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Theme Manager
# Manages desktop themes (Qt, GTK, Compositor) via symlinks and restarts
# UI components to apply changes instantly.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Configuration ---
THEME_DIR="/usr/share/vice-os/themes"
DEFAULT_THEME="neon-miami"

# Target configuration files (these will be symlinked to the active theme)
COMPTON_CONF="/etc/xdg/compton.conf"
GTK_CSS="/etc/gtk-3.0/gtk.css"
GTK_SETTINGS="/etc/gtk-3.0/settings.ini"
QSS_STYLE="/opt/vice-os/style.qss"

# --- Helper Functions ---

check_theme_deps() {
    check_dependencies "ln" "readlink" "pgrep" "pkill"
}

# --- Information Functions ---

list_themes() {
    log_info "Available Themes:"
    echo "==================================="

    if [ ! -d "$THEME_DIR" ]; then
        log_warn "Theme directory $THEME_DIR does not exist."
        return 1
    fi

    local current_theme
    current_theme=$(get_current_theme)

    for dir in "$THEME_DIR"/*/; do
        local theme_name
        theme_name=$(basename "$dir")

        if [ "$theme_name" == "$current_theme" ]; then
            echo "  [Active] $theme_name"
        else
            echo "  [ ]      $theme_name"
        fi
    done

    echo "==================================="
}

get_current_theme() {
    # Determine current theme by reading the symlink of the compton config
    if [ -L "$COMPTON_CONF" ]; then
        local target
        target=$(readlink -f "$COMPTON_CONF")
        # Extract theme name from path: /usr/share/vice-os/themes/neon-miami/compton.conf
        local theme_name
        theme_name=$(echo "$target" | sed "s|$THEME_DIR/||;s|/compton.conf||")
        echo "$theme_name"
    else
        echo "unknown"
    fi
}

show_current() {
    local current
    current=$(get_current_theme)
    log_info "Current Active Theme: $current"
}

# --- Apply Functions ---

validate_theme_exists() {
    local theme="$1"
    local theme_path="${THEME_DIR}/${theme}"

    if [ ! -d "$theme_path" ]; then
        log_error "Theme '$theme' not found in $THEME_DIR."
        log_info "Available themes can be listed with: $0 list"
        return 1
    fi

    # Check if required files exist in the theme directory
    local required_files=("compton.conf" "gtk.css" "settings.ini" "style.qss")
    for file in "${required_files[@]}"; do
        if [ ! -f "${theme_path}/${file}" ]; then
            log_error "Theme '$theme' is incomplete. Missing file: ${file}"
            return 1
        fi
    done

    return 0
}

apply_theme() {
    local theme="$1"

    validate_theme_exists "$theme" || return 1

    local theme_path="${THEME_DIR}/${theme}"

    log_info "Applying theme: $theme..."

    # Backup existing files if they are not symlinks (first run)
    local timestamp
    timestamp=$(date +%Y%m%d%H%M%S)

    for file in "$COMPTON_CONF" "$GTK_CSS" "$GTK_SETTINGS" "$QSS_STYLE"; do
        if [ -f "$file" ] && [ ! -L "$file" ]; then
            log_info "Backing up existing $file to ${file}.backup.${timestamp}"
            mv "$file" "${file}.backup.${timestamp}"
        fi
    done

    # Create symlinks
    log_info "Linking theme files..."
    ln -sf "${theme_path}/compton.conf" "$COMPTON_CONF"
    ln -sf "${theme_path}/gtk.css" "$GTK_CSS"
    ln -sf "${theme_path}/settings.ini" "$GTK_SETTINGS"
    ln -sf "${theme_path}/style.qss" "$QSS_STYLE"

    # Apply UI changes
    restart_ui

    log_success "Theme '$theme' applied successfully."
}

restart_ui() {
    log_info "Restarting UI components..."

    # Restart Picom (Compositor)
    if pgrep -x picom > /dev/null 2>&1; then
        log_info "Restarting Picom..."
        pkill -x picom
        sleep 1
        # Start picom in background (usually handled by openbox autostart)
        /usr/bin/picom -b --config "$COMPTON_CONF" 2>/dev/null || true
    fi

    # Reconfigure Openbox (reloads style.qss for vice_shell if it listens to it, and openbox rc)
    if pgrep -x openbox > /dev/null 2>&1; then
        log_info "Reconfiguring Openbox..."
        openbox --reconfigure
    fi

    # Note: Qt applications usually need a restart to pick up new .qss files.
    # The vice_shell.py would need to be restarted manually or via script if it doesn't auto-reload.
    if pgrep -f "vice_shell.py" > /dev/null 2>&1; then
        log_info "Restarting Desktop Shell..."
        pkill -f "vice_shell.py"
        # The openbox autostart or a process manager should respawn it.
        # For manual execution, we start it here.
        /usr/bin/python3 /opt/vice-os/vice_shell.py &
        disown
    fi
}

reset_theme() {
    log_info "Resetting to default theme: $DEFAULT_THEME"
    apply_theme "$DEFAULT_THEME"
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Theme Manager (GTK / Qt / Openbox)

Usage: $0 <command> [options]

Commands:
  list                 List all available themes
  current              Show the currently active theme
  apply <theme_name>   Apply a specific theme
  reset                Reset to the default theme ($DEFAULT_THEME)
  help                 Show this help message

Notes:
  - Themes are stored in: $THEME_DIR
  - Applying a theme instantly restarts the compositor and desktop shell.
  - Qt applications (like vice_shell) will restart to apply the new Qt stylesheet.

Examples:
  $0 list
  $0 current
  $0 apply synthwave
  $0 reset
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

    check_theme_deps

    case "$command" in
        list|ls)
            list_themes
            ;;
        current|status)
            show_current
            ;;
        apply|set|set-theme)
            local theme="${1:-}"
            if [ -z "$theme" ]; then
                log_error "Theme name required."
                exit 1
            fi
            apply_theme "$theme"
            ;;
        reset|default)
            reset_theme
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