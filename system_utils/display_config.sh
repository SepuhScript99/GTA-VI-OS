#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Display Config Manager
# Manages persistent X11 configuration, DPI scaling, display profiles,
# and Xorg configuration generation.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Configuration ---
PROFILE_DIR="${HOME}/.config/vice-os/display-profiles"
XRANDR_CMD="xrandr"
XORG_CONF_DIR="/etc/X11/xorg.conf.d"
XRESOURCES_FILE="${HOME}/.Xresources"

# --- Helper Functions ---

check_display_config_deps() {
    if [[ "${VICE_TESTING:-0}" == "1" ]]; then
        return 0
    fi
    check_dependencies "xrandr"

    if [ -z "${DISPLAY:-}" ]; then
        log_error "No DISPLAY environment variable set."
        exit 1
    fi
}

ensure_profile_dir() {
    if [ ! -d "$PROFILE_DIR" ]; then
        mkdir -p "$PROFILE_DIR"
    fi
}

# --- Profile Management Functions ---

save_profile() {
    local profile_name="${1:-default}"

    ensure_profile_dir

    local profile_file="${PROFILE_DIR}/${profile_name}.sh"

    log_info "Saving current display configuration as profile: $profile_name"

    # Generate xrandr commands from current state
    local commands=""

    # Get connected displays
    local displays
    displays=$("$XRANDR_CMD" --query | grep " connected" | awk '{print $1}')

    if [ -z "$displays" ]; then
        log_error "No connected displays found."
        return 1
    fi

    # Build xrandr command for each display
    local first_disp=""
    for disp in $displays; do
        if [ -z "$first_disp" ]; then
            first_disp="$disp"
            commands+="xrandr --output \"$disp\" --auto --primary"
        else
            commands+=" --right-of \"$first_disp\""
            commands+=$'\n'xrandr --output \"$disp\" --auto
        fi
    done

    # Write profile script
    cat <<PROFILE > "$profile_file"
#!/bin/bash
# Vice OS Display Profile: $profile_name
# Generated on $(date)
# Run this script to restore this display configuration.

set -e

 $commands
PROFILE

    chmod +x "$profile_file"

    log_success "Profile saved: $profile_file"
    log_info "To apply: $0 load $profile_name"
}

load_profile() {
    local profile_name="${1:-default}"
    local profile_file="${PROFILE_DIR}/${profile_name}.sh"

    if [ ! -f "$profile_file" ]; then
        log_error "Profile '$profile_name' not found."
        log_info "Available profiles:"
        list_profiles
        return 1
    fi

    log_info "Loading display profile: $profile_name"

    if bash "$profile_file"; then
        log_success "Profile '$profile_name' applied successfully."
    else
        log_error "Failed to apply profile '$profile_name'."
        return 1
    fi
}

list_profiles() {
    log_info "Available Display Profiles:"
    echo "==================================="

    ensure_profile_dir

    local found=false
    for file in "$PROFILE_DIR"/*.sh; do
        if [ -f "$file" ]; then
            local name
            name=$(basename "$file" .sh)
            echo "  $name"
            found=true
        fi
    done

    if [ "$found" == false ]; then
        log_info "No profiles saved. Use '$0 save <name>' to create one."
    fi

    echo "==================================="
}

delete_profile() {
    local profile_name="$1"

    if [ -z "$profile_name" ]; then
        log_error "Profile name required."
        return 1
    fi

    local profile_file="${PROFILE_DIR}/${profile_name}.sh"

    if [ ! -f "$profile_file" ]; then
        log_error "Profile '$profile_name' not found."
        return 1
    fi

    rm -f "$profile_file"
    log_success "Profile '$profile_name' deleted."
}

# --- DPI Functions ---

get_dpi() {
    local dpi

    # Try xrandr first
    dpi=$("$XRANDR_CMD" --query | grep -i "DPI" | head -n 1 | awk '{print $NF}' 2>/dev/null || echo "")

    if [ -z "$dpi" ]; then
        # Fallback: calculate from xdpyinfo
        if command -v xdpyinfo > /dev/null 2>&1; then
            dpi=$(xdpyinfo 2>/dev/null | grep "resolution" | awk '{print $2}' | cut -d'x' -f1)
        fi
    fi

    if [ -z "$dpi" ]; then
        echo "96"
    else
        echo "$dpi"
    fi
}

set_dpi() {
    local dpi="$1"

    if ! [[ "$dpi" =~ ^[0-9]+$ ]] || [ "$dpi" -lt 50 ] || [ "$dpi" -gt 400 ]; then
        log_error "DPI must be a number between 50 and 400."
        return 1
    fi

    log_info "Setting DPI to: $dpi"

    # Set X resources DPI
    if command -v xrdb > /dev/null 2>&1; then
        xrdb -merge <<XRES
Xft.dpi: $dpi
Xcursor.size: $((dpi / 4))
XRES
        log_info "Xft.dpi set to $dpi"
    fi

    # Set xrandr DPI
    "$XRANDR_CMD" --dpi "$dpi" 2>/dev/null || true

    # Update Xresources file for persistence
    if [ -f "$XRESOURCES_FILE" ]; then
        sed -i "/^Xft.dpi:/d" "$XRESOURCES_FILE"
        sed -i "/^Xcursor.size:/d" "$XRESOURCES_FILE"
    fi
    echo "Xft.dpi: $dpi" >> "$XRESOURCES_FILE"
    echo "Xcursor.size: $((dpi / 4))" >> "$XRESOURCES_FILE"

    # Update Qt scaling
    local scale_factor
    scale_factor=$(awk "BEGIN {printf \"%.2f\", $dpi / 96.0}")
    export QT_AUTO_SCREEN_SCALE_FACTOR=1

    # Update GDK scaling for GTK apps
    export GDK_DPI_SCALE="$scale_factor"

    log_success "DPI set to: $dpi (Scale: ${scale_factor}x)"
    log_warn "Log out and log back in for all applications to pick up the new DPI."
}

# --- Xorg Configuration Functions ---

generate_xorg_conf() {
    local output_file="${1:-/etc/X11/xorg.conf}"

    log_info "Generating Xorg configuration..."

    local card_bus_id
    card_bus_id=$(lspci | grep -i "vga\|3d\|display" | head -n 1 | awk '{print $1}')

    if [ -z "$card_bus_id" ]; then
        log_error "No graphics card found in lspci."
        return 1
    fi

    # Convert PCI bus ID to Xorg format (e.g., 00:02.0 -> PCI:0:2:0)
    local xorg_bus_id
    xorg_bus_id=$(echo "$card_bus_id" | sed 's/^0*//; s/:0*/:/g; s/^/PCI:/' | sed 's/\.0$//')

    cat <<XORG_CONF > "$output_file"
# Generated by Vice OS Display Config Manager on $(date)

Section "ServerLayout"
    Identifier     "X.org Configured"
    Screen      0  "Screen0" 0 0
    InputDevice    "Mouse0" "CorePointer"
    InputDevice    "Keyboard0" "CoreKeyboard"
EndSection

Section "Files"
    ModulePath   "/usr/lib/xorg/modules"
    FontPath     "/usr/share/fonts/X11/misc/"
    FontPath     "/usr/share/fonts/X11/Type1/"
    FontPath     "/usr/share/fonts/X11/75dpi/"
    FontPath     "/usr/share/fonts/X11/100dpi/"
EndSection

Section "Module"
    Load  "glx"
EndSection

Section "InputDevice"
    Identifier  "Keyboard0"
    Driver      "kbd"
EndSection

Section "InputDevice"
    Identifier  "Mouse0"
    Driver      "mouse"
    Option      "Protocol" "auto"
    Option      "Device" "/dev/input/mice"
    Option      "ZAxisMapping" "4 5 6 7"
EndSection

Section "Monitor"
    Identifier   "Monitor0"
    VendorName   "Monitor Vendor"
    ModelName    "Monitor Model"
EndSection

Section "Device"
    Identifier  "Card0"
    Driver      "modesetting"
    BusID       "$xorg_bus_id"
EndSection

Section "Screen"
    Identifier "Screen0"
    Device     "Card0"
    Monitor    "Monitor0"
    SubSection "Display"
        Viewport   0 0
        Depth     24
    EndSubSection
EndSection
XORG_CONF

    log_success "Xorg configuration generated: $output_file"
    log_info "Bus ID detected: $xorg_bus_id"
    log_warn "Review the configuration before restarting X."
}

# --- Persistence Functions ---

enable_persistence() {
    local profile_name="${1:-default}"

    ensure_profile_dir

    local profile_file="${PROFILE_DIR}/${profile_name}.sh"

    if [ ! -f "$profile_file" ]; then
        log_warn "Profile '$profile_name' doesn't exist. Creating from current state..."
        save_profile "$profile_name"
    fi

    local autostart_file="${HOME}/.config/openbox/display-restore.sh"

    cat <<AUTOSTART > "$autostart_file"
#!/bin/bash
# Vice OS Display Restore Script
# Restores display profile on login
bash "$profile_file"
AUTOSTART

    chmod +x "$autostart_file"

    log_success "Display persistence enabled."
    log_info "Profile '$profile_name' will be applied on every login."
}

disable_persistence() {
    local autostart_file="${HOME}/.config/openbox/display-restore.sh"

    if [ -f "$autostart_file" ]; then
        rm -f "$autostart_file"
        log_success "Display persistence disabled."
    else
        log_info "Persistence was not enabled."
    fi
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Display Config Manager

Usage: $0 <command> [options]

Profile Management:
  save [name]                 Save current display setup as a profile (default: 'default')
  load [name]                 Load and apply a display profile
  list                        List all saved profiles
  delete <name>               Delete a saved profile

DPI Scaling:
  get-dpi                     Show current DPI setting
  set-dpi <value>             Set DPI (50-400, default: 96)

Xorg Configuration:
  generate-xorg [output_file] Generate xorg.conf (default: /etc/X11/xorg.conf)

Persistence:
  enable-persistence [name]   Enable auto-apply of profile on login
  disable-persistence         Disable auto-apply on login

Help:
  help                        Show this help message

Notes:
  - This utility handles persistent configuration.
  - For runtime display operations (resolution, rotation), use 'display_manager.sh'.
  - DPI changes require logout/login for full effect.
  - Xorg config generation requires root privileges (use sudo).

Examples:
  $0 save office-setup
  $0 load office-setup
  $0 set-dpi 144
  $0 get-dpi
  $0 generate-xorg
  $0 enable-persistence office-setup
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

    check_display_config_deps

    case "$command" in
        save|save-profile)
            local name="${1:-default}"
            save_profile "$name"
            ;;
        load|load-profile|apply)
            local name="${1:-default}"
            load_profile "$name"
            ;;
        list|ls|profiles)
            list_profiles
            ;;
        delete|rm|remove)
            local name="${1:-}"
            if [ -z "$name" ]; then
                log_error "Profile name required."
                exit 1
            fi
            delete_profile "$name"
            ;;
        get-dpi|dpi)
            get_dpi
            ;;
        set-dpi)
            local dpi="${1:-}"
            if [ -z "$dpi" ]; then
                log_error "DPI value required."
                exit 1
            fi
            set_dpi "$dpi"
            ;;
        generate-xorg|xorg-conf)
            local output="${1:-/etc/X11/xorg.conf}"
            generate_xorg_conf "$output"
            ;;
        enable-persistence|enable)
            local name="${1:-default}"
            enable_persistence "$name"
            ;;
        disable-persistence|disable)
            disable_persistence
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