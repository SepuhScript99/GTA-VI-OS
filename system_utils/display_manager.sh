#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Display Manager
# Provides display configuration utilities: resolution, multi-monitor,
# mirroring, and rotation using xrandr.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Helper Functions ---

check_display_deps() {
    if [[ "${VICE_TESTING:-0}" == "1" ]]; then
        return 0
    fi
    check_dependencies "xrandr"

    if [ -z "${DISPLAY:-}" ]; then
        log_error "No DISPLAY environment variable set. This script must be run from an X session."
        exit 1
    fi
}

get_connected_displays() {
    xrandr --query | grep " connected" | awk '{print $1}'
}

get_primary_display() {
    xrandr --query | grep " connected primary" | awk '{print $1}'
}

get_display_modes() {
    local display="$1"
    xrandr --query | grep -A 20 "^${display} connected" | grep -v "^${display}" | grep -v "disconnected" | awk '{print $1}' | sort -u
}

# --- Display Information Functions ---

list_displays() {
    log_info "Connected Displays:"
    local displays
    displays=$(get_connected_displays)

    if [ -z "$displays" ]; then
        log_warn "No connected displays found."
        return 1
    fi

    local primary
    primary=$(get_primary_display)

    for disp in $displays; do
        local resolution rate
        resolution=$(xrandr --query | grep "^${disp}" | grep -o '[0-9]*x[0-9]*+[0-9]*+[0-9]*' | head -n 1)
        rate=$(xrandr --query | grep "^${disp}" | grep -o '[0-9]*\.[0-9]*Hz\|[0-9]*Hz' | head -n 1)

        if [ "$disp" == "$primary" ]; then
            echo "  - $disp (Primary): $resolution @ $rate"
        else
            echo "  - $disp: $resolution @ $rate"
        fi
    done
}

show_resolutions() {
    local display="${1:-}"

    if [ -z "$display" ]; then
        display=$(get_primary_display)
        if [ -z "$display" ]; then
            display=$(get_connected_displays | head -n 1)
        fi
    fi

    if [ -z "$display" ]; then
        log_error "No display specified and no primary display found."
        return 1
    fi

    log_info "Available resolutions for $display:"
    get_display_modes "$display" | while read -r mode; do
        echo "  - $mode"
    done
}

# --- Configuration Functions ---

set_resolution() {
    local display="$1"
    local resolution="$2"

    log_info "Setting resolution for $display to $resolution..."

    if ! xrandr --output "$display" --mode "$resolution"; then
        log_error "Failed to set resolution $resolution on $display."
        log_info "Check available resolutions with: $0 resolutions $display"
        return 1
    fi

    log_success "Resolution set successfully."
}

set_primary() {
    local display="$1"

    log_info "Setting $display as primary display..."

    if ! xrandr --output "$display" --primary; then
        log_error "Failed to set $display as primary."
        return 1
    fi

    log_success "$display set as primary display."
}

enable_display() {
    local display="$1"

    log_info "Enabling $display..."

    if ! xrandr --output "$display" --auto; then
        log_error "Failed to enable $display."
        return 1
    fi

    log_success "$display enabled."
}

disable_display() {
    local display="$1"

    log_info "Disabling $display..."

    if ! xrandr --output "$display" --off; then
        log_error "Failed to disable $display."
        return 1
    fi

    log_success "$display disabled."
}

arrange_display() {
    local display="$1"
    local position="$2"
    local relative_to="$3"

    case "$position" in
        left-of|right-of|above|below|same-as)
            ;;
        *)
            log_error "Invalid position: $position"
            log_info "Valid positions: left-of, right-of, above, below, same-as"
            return 1
            ;;
    esac

    log_info "Arranging $display $position $relative_to..."

    if ! xrandr --output "$display" --$position "$relative_to"; then
        log_error "Failed to arrange $display $position $relative_to."
        return 1
    fi

    log_success "Display arrangement applied."
}

mirror_display() {
    local source="$1"
    local target="$2"

    log_info "Mirroring $source to $target..."

    if ! xrandr --output "$target" --same-as "$source"; then
        log_error "Failed to mirror $source to $target."
        return 1
    fi

    log_success "Mirroring enabled."
}

rotate_display() {
    local display="$1"
    local rotation="$2"

    case "$rotation" in
        normal|left|right|inverted)
            ;;
        *)
            log_error "Invalid rotation: $rotation"
            log_info "Valid rotations: normal, left, right, inverted"
            return 1
            ;;
    esac

    log_info "Rotating $display to $rotation..."

    if ! xrandr --output "$display" --rotation "$rotation"; then
        log_error "Failed to rotate $display."
        return 1
    fi

    log_success "Display rotated to $rotation."
}

# --- Auto Configuration ---

auto_configure() {
    log_info "Auto-configuring displays..."

    local displays
    displays=$(get_connected_displays)

    if [ -z "$displays" ]; then
        log_error "No connected displays found."
        return 1
    fi

    local first_disp
    first_disp=$(echo "$displays" | head -n 1)

    log_info "Setting $first_disp as primary..."
    xrandr --output "$first_disp" --primary --auto

    # Arrange remaining displays to the right
    local prev_disp="$first_disp"
    for disp in $displays; do
        if [ "$disp" != "$first_disp" ]; then
            log_info "Placing $disp to the right of $prev_disp..."
            xrandr --output "$disp" --auto --right-of "$prev_disp"
            prev_disp="$disp"
        fi
    done

    log_success "Auto-configuration complete."
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Display Manager

Usage: $0 <command> [options]

Configuration:
Commands:
  list                           List connected displays
  resolutions [display]          Show available resolutions for a display

Configuration:
  set-resolution <display> <WxH> Set resolution (e.g., 1920x1080)
  set-primary <display>          Set primary display
  enable <display>               Enable a display
  disable <display>              Disable a display
  arrange <display> <pos> <ref>  Arrange display (pos: left-of, right-of, above, below, same-as)
  mirror <source> <target>       Mirror source display to target
  rotate <display> <rotation>    Rotate display (normal, left, right, inverted)

Utility:
  auto                           Auto-configure all connected displays
  help                           Show this help message

Examples:
  $0 list
  $0 set-resolution HDMI-1 1920x1080
  $0 arrange DP-1 right-of HDMI-1
  $0 rotate eDP-1 left
  $0 auto
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

    check_display_deps

    case "$command" in
        list)
            list_displays
            ;;
        resolutions|res)
            local display="${1:-}"
            show_resolutions "$display"
            ;;
        set-resolution|set-res)
            local display="${1:-}"
            local resolution="${2:-}"
            if [ -z "$display" ] || [ -z "$resolution" ]; then
                log_error "Display and resolution required."
                log_info "Usage: $0 set-resolution <display> <WxH>"
                exit 1
            fi
            set_resolution "$display" "$resolution"
            ;;
        set-primary)
            local display="${1:-}"
            if [ -z "$display" ]; then
                log_error "Display required."
                exit 1
            fi
            set_primary "$display"
            ;;
        enable)
            local display="${1:-}"
            if [ -z "$display" ]; then
                log_error "Display required."
                exit 1
            fi
            enable_display "$display"
            ;;
        disable)
            local display="${1:-}"
            if [ -z "$display" ]; then
                log_error "Display required."
                exit 1
            fi
            disable_display "$display"
            ;;
        arrange)
            local display="${1:-}"
            local position="${2:-}"
            local relative_to="${3:-}"
            if [ -z "$display" ] || [ -z "$position" ] || [ -z "$relative_to" ]; then
                log_error "Display, position, and reference display required."
                log_info "Usage: $0 arrange <display> <left-of|right-of|above|below|same-as> <ref-display>"
                exit 1
            fi
            arrange_display "$display" "$position" "$relative_to"
            ;;
        mirror)
            local source="${1:-}"
            local target="${2:-}"
            if [ -z "$source" ] || [ -z "$target" ]; then
                log_error "Source and target displays required."
                exit 1
            fi
            mirror_display "$source" "$target"
            ;;
        rotate)
            local display="${1:-}"
            local rotation="${2:-}"
            if [ -z "$display" ] || [ -z "$rotation" ]; then
                log_error "Display and rotation required."
                exit 1
            fi
            rotate_display "$display" "$rotation"
            ;;
        auto)
            auto_configure
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