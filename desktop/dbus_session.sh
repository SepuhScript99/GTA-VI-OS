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
    log_warn() { echo "[WARN] $1" >&2; }
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

    # 3. Start the user DBus session if missing or pointing to a stale/non-existent socket
    if [ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ]; then
        case "$DBUS_SESSION_BUS_ADDRESS" in
            unix:path=*)
                dbus_sock="${DBUS_SESSION_BUS_ADDRESS#unix:path=}"
                dbus_sock="${dbus_sock%%,*}"
                if [ ! -S "$dbus_sock" ]; then
                    log_warn "Stale DBUS_SESSION_BUS_ADDRESS ($dbus_sock missing); starting fresh session bus..."
                    unset DBUS_SESSION_BUS_ADDRESS
                fi
                ;;
        esac
    fi
    if [ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]; then
        if [ -S "$XDG_RUNTIME_DIR/bus" ]; then
            export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
        elif command -v dbus-launch > /dev/null 2>&1; then
            log_info "Starting DBus session bus..."
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

    # 6. Start PipeWire/PulseAudio only if not already managed by systemd or running
    if [ ! -S "$XDG_RUNTIME_DIR/pulse/native" ] && \
       ! pgrep -u "$(id -u)" -x pipewire > /dev/null 2>&1 && \
       ! pgrep -u "$(id -u)" -x pipewire-pulse > /dev/null 2>&1; then
        if command -v systemctl > /dev/null 2>&1 && systemctl --user status > /dev/null 2>&1; then
            log_info "Starting PipeWire via systemd user session..."
            systemctl --user start pipewire pipewire-pulse wireplumber 2>/dev/null || true
        elif command -v pipewire > /dev/null 2>&1; then
            log_info "Starting PipeWire..."
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

    # 7. Launch session watchdog (auto-restarts vice_shell.py on crash)
    if [ -f /opt/vice-os/session_watchdog.py ]; then
        log_info "Starting session watchdog..."
        nohup python3 /opt/vice-os/session_watchdog.py > /dev/null 2>&1 &
        disown
    else
        log_warn "session_watchdog.py not found. Shell crash recovery disabled."
    fi

    # 8. Hand off to the window manager
    log_info "Launching Openbox session..."
    if command -v openbox-session > /dev/null 2>&1; then
        exec openbox-session
    else
        log_error "openbox-session not found! Falling back to xterm."
        exec xterm
    fi
}

main "$@"
