#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Wayland Session Initializer
#
# Starts a user DBus session, PipeWire/WirePlumber audio (with ALSA/sink
# unmute), and environment variables, then hands off to labwc (Wayland compositor).
# ============================================================================

# Source the shared library if available (for consistent logging)
if [ -f /opt/vice-os/lib/common.sh ]; then
    source /opt/vice-os/lib/common.sh
else
    log_info() { echo "[INFO] $1"; }
    log_error() { echo "[ERROR] $1" >&2; }
    log_warn() { echo "[WARN] $1" >&2; }
fi

start_audio_stack() {
    # Prefer systemd --user when active
    if command -v systemctl > /dev/null 2>&1 && timeout 3 systemctl --user show-environment > /dev/null 2>&1; then
        log_info "Starting PipeWire via systemd user session..."
        timeout 5 systemctl --user start pipewire.socket pipewire-pulse.socket pipewire.service wireplumber.service pipewire-pulse.service 2>/dev/null || true
    fi

    # Fallback / verification for sessions launched without active systemd --user
    if command -v pipewire > /dev/null 2>&1; then
        if ! pgrep -u "$(id -u)" -x pipewire > /dev/null 2>&1; then
            log_info "Starting PipeWire daemon directly..."
            nohup /usr/bin/pipewire > /dev/null 2>&1 &
            local w=0
            while [ "$w" -lt 20 ] && [ ! -S "$XDG_RUNTIME_DIR/pipewire-0" ]; do
                sleep 0.1
                w=$((w + 1))
            done
        fi
        if command -v wireplumber > /dev/null 2>&1 && ! pgrep -u "$(id -u)" -x wireplumber > /dev/null 2>&1; then
            nohup /usr/bin/wireplumber > /dev/null 2>&1 &
        fi
        if command -v pipewire-pulse > /dev/null 2>&1 && ! pgrep -u "$(id -u)" -x pipewire-pulse > /dev/null 2>&1; then
            nohup /usr/bin/pipewire-pulse > /dev/null 2>&1 &
        fi
    elif ! pgrep -u "$(id -u)" -x pulseaudio > /dev/null 2>&1; then
        if command -v pulseaudio > /dev/null 2>&1; then
            log_info "Starting PulseAudio..."
            /usr/bin/pulseaudio --start --log-target=syslog || true
        fi
    fi

    # Immediately unmute ALSA hardware playback controls across detected cards
    if command -v amixer > /dev/null 2>&1 && [ -r /proc/asound/cards ]; then
        local card
        for card in $(awk '/^[[:space:]]*[0-9]+/ {print $1}' /proc/asound/cards 2>/dev/null || true); do
            local ctrl
            for ctrl in Master PCM Front Surround Center LFE Side Headphone Speaker; do
                amixer -c "$card" sset "$ctrl" 85% unmute > /dev/null 2>&1 || true
            done
        done
    fi

    # Set default Pulse/PipeWire sink unmuted at 85% once a real audio sink appears
    (
        local i=0
        while [ "$i" -lt 25 ]; do
            if [ -S "$XDG_RUNTIME_DIR/pulse/native" ] && command -v pactl > /dev/null 2>&1; then
                if timeout 2 pactl info > /dev/null 2>&1; then
                    local sink
                    sink=$(timeout 2 pactl get-default-sink 2>/dev/null || true)
                    if [ -n "$sink" ] && [ "$sink" != "auto_null" ] && [ "$sink" != "@DEFAULT_SINK@" ]; then
                        timeout 2 pactl set-sink-mute "$sink" 0 > /dev/null 2>&1 || true
                        timeout 2 pactl set-sink-volume "$sink" 85% > /dev/null 2>&1 || true
                        exit 0
                    fi
                fi
            elif command -v wpctl > /dev/null 2>&1; then
                if timeout 2 wpctl get-volume @DEFAULT_AUDIO_SINK@ > /dev/null 2>&1; then
                    timeout 2 wpctl set-mute @DEFAULT_AUDIO_SINK@ 0 > /dev/null 2>&1 || true
                    timeout 2 wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.85 > /dev/null 2>&1 || true
                    exit 0
                fi
            fi
            sleep 0.2
            i=$((i + 1))
        done
    ) &
}

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

    # 4. Set Wayland-specific environment variables
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

    # 5. Push environment variables to DBus activation environment
    log_info "Updating DBus activation environment..."
    if command -v dbus-update-activation-environment > /dev/null 2>&1; then
        dbus-update-activation-environment --all --systemd 2>/dev/null || true
    fi

    # Safely import environment to systemd user session
    if command -v systemctl > /dev/null 2>&1; then
        timeout 5 systemctl --user import-environment \
            XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS \
            XDG_SESSION_TYPE XDG_CURRENT_DESKTOP WAYLAND_DISPLAY \
            QT_QPA_PLATFORM QT_QPA_PLATFORMTHEME QT_AUTO_SCREEN_SCALE_FACTOR \
            MOZ_ENABLE_WAYLAND 2>/dev/null || true
    fi

    # 6. Start PipeWire/WirePlumber/pipewire-pulse and set default 85% unmuted levels
    start_audio_stack

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
        exec labwc
    else
        log_error "labwc not found! Cannot start Wayland session."
        log_error "Falling back to a shell prompt. Install labwc to use Wayland."
        exec bash
    fi
}

main "$@"
