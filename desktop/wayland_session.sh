#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Wayland Session Initializer
#
# Starts a user DBus session, Pipewire audio, and environment variables,
# then hands off to labwc (the Wayland compositor).
#
# This is the Wayland counterpart to dbus_session.sh (which launches the
# X11/Openbox session). The key differences are:
#   - No X server / xinit (labwc is the display server)
#   - No login.py greeter (the compositor starts directly after env setup)
#   - XDG_SESSION_TYPE=wayland (enables native Wayland Qt5 platform)
#   - XWayland provides backward compatibility for X11 applications
#
# Security note: This session does not use the login.py password screen.
# The system auto-logins via getty (same as X11 mode). Idle screen locking
# can be added separately via swaylock in a future enhancement.
# ============================================================================

# Source the shared library if available (for consistent logging)
if [ -f /opt/vice-os/lib/common.sh ]; then
    source /opt/vice-os/lib/common.sh
else
    log_info() { echo "[INFO] $1"; }
    log_error() { echo "[ERROR] $1" >&2; }
    log_warn() { echo "[WARN] $1" >&2; }
fi

main() {
    log_info "Initializing Wayland desktop session environment..."

    # 1. Ensure PATH is set for the session
    export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

    # 2. Ensure XDG_RUNTIME_DIR exists and is set
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
    if [ ! -d "$XDG_RUNTIME_DIR" ]; then
        mkdir -p "$XDG_RUNTIME_DIR"
        chmod 700 "$XDG_RUNTIME_DIR"
    fi

    # 3. Start the user DBus session if not already running
    if [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]; then
        log_info "Starting DBus session bus..."
        if command -v dbus-launch > /dev/null 2>&1; then
            eval "$(dbus-launch --sh-syntax)"
            export DBUS_SESSION_BUS_ADDRESS
            export DBUS_SESSION_BUS_PID
        else
            log_error "dbus-launch not found. Desktop integration will be limited."
        fi
    fi

    # 4. Push environment variables to DBus activation environment
    log_info "Updating DBus activation environment..."
    if command -v dbus-update-activation-environment > /dev/null 2>&1; then
        dbus-update-activation-environment --all --systemd 2>/dev/null || true
    fi

    # Safely import environment to systemd user session
    if command -v systemctl > /dev/null 2>&1; then
        timeout 5 systemctl --user import-environment \
            XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS \
            XDG_SESSION_TYPE XDG_CURRENT_DESKTOP WAYLAND_DISPLAY 2>/dev/null || true
    fi

    # 5. Set Wayland-specific environment variables
    export XDG_SESSION_TYPE="wayland"
    export XDG_CURRENT_DESKTOP="labwc"
    export XDG_SESSION_DESKTOP="labwc"
    export DESKTOP_SESSION="labwc"

    # Qt5: prefer native Wayland, fall back to X11 (xcb) via XWayland
    export QT_QPA_PLATFORM="wayland;xcb"
    export QT_AUTO_SCREEN_SCALE_FACTOR=1
    export QT_QPA_PLATFORMTHEME="qt5ct"

    # Enable native Wayland for Firefox
    export MOZ_ENABLE_WAYLAND=1

    # 6. Start Pipewire if not running
    if ! pgrep -u "$(id -u)" -x pipewire > /dev/null 2>&1; then
        if command -v pipewire > /dev/null 2>&1; then
            log_info "Starting Pipewire..."
            /usr/bin/pipewire &
            /usr/bin/pipewire-pulse &
            if command -v wireplumber > /dev/null 2>&1; then
                /usr/bin/wireplumber &
            fi
        elif ! pgrep -u "$(id -u)" -x pulseaudio > /dev/null 2>&1; then
            if command -v pulseaudio > /dev/null 2>&1; then
                log_info "Starting PulseAudio..."
                /usr/bin/pulseaudio --start --log-target=syslog
            fi
        fi
    fi

    # 7. Start session watchdog (auto-restarts vice_shell.py on crash)
    if [ -f /opt/vice-os/session_watchdog.py ]; then
        log_info "Starting session watchdog..."
        nohup python3 /opt/vice-os/session_watchdog.py > /dev/null 2>&1 &
        disown
    else
        log_warn "session_watchdog.py not found. Shell crash recovery disabled."
    fi

    # 8. Hand off to the Wayland compositor
    log_info "Launching labwc Wayland compositor..."
    if command -v labwc > /dev/null 2>&1; then
        # labwc reads config from ~/.config/labwc/ by default.
        # A system-wide fallback can be placed in /etc/xdg/labwc/.
        exec labwc
    else
        log_error "labwc not found! Cannot start Wayland session."
        log_error "Falling back to a shell prompt. Install labwc to use Wayland."
        exec bash
    fi
}

main "$@"
