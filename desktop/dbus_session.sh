#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) DBus Session Initializer
# Starts a user DBus session, loads Xresources, ensures PipeWire/WirePlumber
# and ALSA/Pulse sink levels are active and unmuted before handing off to Openbox.
# ============================================================================

# Source the shared library if available (for consistent logging)
if [ -f /opt/vice-os/lib/common.sh ]; then
    source /opt/vice-os/lib/common.sh
else
    log_info() { echo "[INFO] $1"; }
    log_warn() { echo "[WARN] $1" >&2; }
    log_error() { echo "[ERROR] $1" >&2; }
fi

start_audio_stack() {
    # Prefer systemd --user when active (started via PAM/logind)
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
    export XDG_SESSION_TYPE="${XDG_SESSION_TYPE:-x11}"
    export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
    export QT_AUTO_SCREEN_SCALE_FACTOR="${QT_AUTO_SCREEN_SCALE_FACTOR:-1}"
    export QT_QPA_PLATFORMTHEME="${QT_QPA_PLATFORMTHEME:-qt5ct}"
    export MOZ_ENABLE_WAYLAND=0
    export SAL_USE_VCLPLUGIN=gtk3
    if command -v dbus-update-activation-environment > /dev/null 2>&1; then
        dbus-update-activation-environment --all --systemd 2>/dev/null || true
    fi

    # Safely import environment to systemd user session without hanging
    if command -v systemctl > /dev/null 2>&1; then
        timeout 5 systemctl --user import-environment DISPLAY XAUTHORITY XDG_RUNTIME_DIR DBUS_SESSION_BUS_ADDRESS XDG_SESSION_TYPE QT_QPA_PLATFORMTHEME QT_AUTO_SCREEN_SCALE_FACTOR SAL_USE_VCLPLUGIN 2>/dev/null || true
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

    # 6. Start PipeWire/WirePlumber/pipewire-pulse and set default 85% unmuted levels
    start_audio_stack

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
