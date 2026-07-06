#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) DBus Session Initializer
# Starts a user DBus session, loads Xresources, and launches PulseAudio/Pipewire
# before handing off to Openbox. Required because we bypass display managers.
# ============================================================================

# Source the shared library if available (for consistent logging)
if [ -f /opt/vice-os/lib/common.sh ]; then
    source /opt/vice-os/lib/common.sh
else
    log_info() { echo "[INFO] $1"; }
    log_error() { echo "[ERROR] $1" >&2; }
fi

main() {
    log_info "Initializing desktop session environment..."

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

    # 4. Push environment variables to DBus and Systemd user session
    log_info "Updating DBus activation environment..."
    if command -v dbus-update-activation-environment > /dev/null 2>&1; then
        # We include XAUTHORITY here to ensure DBus activated apps can connect to X
        export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
        dbus-update-activation-environment --all --systemd 2>/dev/null || true
    fi

    # Safely import environment to systemd user session without hanging
    if command -v systemctl > /dev/null 2>&1; then
        timeout 5 systemctl --user import-environment DISPLAY XAUTHORITY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS 2>/dev/null || true
    fi

    # 5. Load Xresources (CRITICAL: Openbox does not do this automatically)
    if command -v xrdb > /dev/null 2>&1; then
        if [ -f "$HOME/.Xresources" ]; then
            log_info "Loading Xresources for terminal theming..."
            xrdb -merge "$HOME/.Xresources"
        fi
    else
        log_warn "xrdb not found. Skipping Xresources loading."
    fi

    # 6. Start PulseAudio/Pipewire if not running
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

    # 7. Hand off to the window manager
    log_info "Launching Openbox session..."
    if command -v openbox-session > /dev/null 2>&1; then
        exec openbox-session
    else
        log_error "openbox-session not found! Falling back to xterm."
        exec xterm
    fi
}

main "$@"