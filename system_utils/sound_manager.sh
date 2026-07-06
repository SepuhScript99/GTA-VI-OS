#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Sound Manager
# Manages sound card detection, ALSA configuration, audio testing,
# and audio server status monitoring.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
APLAY_CMD="aplay"
ARECORD_CMD="arecord"
PACTL_CMD="pactl"
SYSTEMCTL_CMD="systemctl"
ALSA_CONF_DIR="/etc/alsa"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Sound operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_sound_deps() {
    check_dependencies "aplay" "arecord"
    
    if ! command -v "$PACTL_CMD" > /dev/null 2>&1; then
        log_warn "pactl not found. Audio server status will be limited."
    fi
}

# --- Sound Card Detection Functions ---

list_sound_cards() {
    log_info "Sound Cards:"
    echo "==================================="
    
    # Use aplay -l for detailed listing
    "$APLAY_CMD" -l 2>/dev/null || true
    
    echo "==================================="
}

list_playback_devices() {
    log_info "Playback Devices:"
    echo "==================================="
    
    "$APLAY_CMD" -L 2>/dev/null || true
    
    echo "==================================="
}

list_capture_devices() {
    log_info "Capture Devices (Microphones):"
    echo "==================================="
    
    "$ARECORD_CMD" -L 2>/dev/null || true
    
    echo "==================================="
}

show_default_devices() {
    log_info "Default Audio Devices:"
    echo "==================================="
    
    if command -v "$PACTL_CMD" > /dev/null 2>&1; then
        local default_sink default_source
        
        default_sink=$("$PACTL_CMD" get-default-sink 2>/dev/null || echo "N/A")
        default_source=$("$PACTL_CMD" get-default-source 2>/dev/null || echo "N/A")
        
        echo "Default Sink (Output):   $default_sink"
        echo "Default Source (Input): $default_source"
        
        # Show details for default sink
        if [ "$default_sink" != "N/A" ]; then
            echo ""
            echo "Default Sink Details:"
            "$PACTL_CMD" list sinks 2>/dev/null | grep -A 15 "Name: $default_sink" || true
        fi
        
        # Show details for default source
        if [ "$default_source" != "N/A" ]; then
            echo ""
            echo "Default Source Details:"
            "$PACTL_CMD" list sources 2>/dev/null | grep -A 15 "Name: $default_source" || true
        fi
    else
        log_warn "pactl not found. Cannot retrieve default devices."
    fi
    
    echo "==================================="
}

# --- Audio Server Status Functions ---

show_server_status() {
    log_info "Audio Server Status:"
    echo "==================================="
    
    # Check PipeWire
    local pipewire_running=false
    if "$SYSTEMCTL_CMD" --user is-active --quiet pipewire 2>/dev/null; then
        echo "PipeWire:               [Running]"
        pipewire_running=true
        
        # Show PipeWire version
        if command -v pipewire > /dev/null 2>&1; then
            local pw_version
            pw_version=$(pipewire --version 2>/dev/null | head -n 1 || echo "Unknown")
            echo "PipeWire Version:       $pw_version"
        fi
    else
        echo "PipeWire:               [Stopped]"
    fi
    
    # Check PipeWire-Pulse
    if "$SYSTEMCTL_CMD" --user is-active --quiet pipewire-pulse 2>/dev/null; then
        echo "PipeWire-Pulse:         [Running]"
    else
        echo "PipeWire-Pulse:         [Stopped]"
    fi
    
    # Check WirePlumber
    if "$SYSTEMCTL_CMD" --user is-active --quiet wireplumber 2>/dev/null; then
        echo "WirePlumber:            [Running]"
    else
        echo "WirePlumber:            [Stopped]"
    fi
    
    # Check PulseAudio (legacy fallback)
    if [ "$pipewire_running" == false ]; then
        if "$SYSTEMCTL_CMD" --user is-active --quiet pulseaudio 2>/dev/null; then
            echo "PulseAudio:             [Running]"
        else
            echo "PulseAudio:             [Stopped]"
        fi
    fi
    
    # Check JACK
    if "$SYSTEMCTL_CMD" --user is-active --quiet jackaudio 2>/dev/null; then
        echo "JACK Audio:             [Running]"
    else
        echo "JACK Audio:             [Stopped]"
    fi
    
    echo ""
    echo "ALSA State:"
    if [ -f /proc/asound/version ]; then
        echo "  ALSA Version:         $(cat /proc/asound/version)"
    fi
    
    if [ -f /proc/asound/cards ]; then
        local card_count
        card_count=$(grep -c "^\s*[0-9]" /proc/asound/cards 2>/dev/null || echo "0")
        echo "  Sound Cards:          $card_count"
    fi
    
    echo "==================================="
}

restart_audio_server() {
    log_info "Restarting Audio Server..."
    
    local restarted=false
    
    # Try restarting PipeWire stack first
    if "$SYSTEMCTL_CMD" --user is-active --quiet pipewire 2>/dev/null; then
        log_info "Restarting PipeWire..."
        "$SYSTEMCTL_CMD" --user restart pipewire
        "$SYSTEMCTL_CMD" --user restart pipewire-pulse 2>/dev/null || true
        "$SYSTEMCTL_CMD" --user restart wireplumber 2>/dev/null || true
        restarted=true
    elif "$SYSTEMCTL_CMD" --user is-active --quiet pulseaudio 2>/dev/null; then
        log_info "Restarting PulseAudio..."
        "$SYSTEMCTL_CMD" --user restart pulseaudio
        restarted=true
    fi
    
    if [ "$restarted" == true ]; then
        sleep 2
        log_success "Audio server restarted."
    else
        log_error "No audio server found to restart."
        return 1
    fi
}

# --- Testing Functions ---

test_speaker() {
    local device="${1:-}"
    local duration="${2:-3}"
    
    log_info "Testing speaker..."
    
    # Find a test sound file
    local test_file=""
    for file in /usr/share/sounds/alsa/*; do
        if [ -f "$file" ]; then
            test_file="$file"
            break
        fi
    done
    
    if [ -n "$test_file" ]; then
        log_info "Playing test sound: $(basename "$test_file")"
        if [ -n "$device" ]; then
            "$APLAY_CMD" -D "$device" "$test_file" 2>/dev/null
        else
            "$APLAY_CMD" "$test_file" 2>/dev/null
        fi
        log_success "Speaker test complete."
    else
        # Fallback: generate a tone
        log_info "No test sound file found. Generating tone..."
        if command -v speaker-test > /dev/null 2>&1; then
            speaker-test -t sine -f 440 -l 1 -p "$duration" 2>/dev/null
            log_success "Speaker test complete."
        else
            log_error "No test sound files or speaker-test available."
            log_info "Install 'alsa-utils' for test sounds."
            return 1
        fi
    fi
}

test_microphone() {
    local duration="${1:-3}"
    local device="${2:-}"
    
    log_info "Testing microphone (recording ${duration}s)..."
    
    local tmp_file
    tmp_file=$(mktemp --suffix=.wav)
    
    if [ -n "$device" ]; then
        "$ARECORD_CMD" -D "$device" -d "$duration" -f cd "$tmp_file" 2>/dev/null
    else
        "$ARECORD_CMD" -d "$duration" -f cd "$tmp_file" 2>/dev/null
    fi
    
    if [ -f "$tmp_file" ] && [ -s "$tmp_file" ]; then
        log_success "Microphone test recorded. Playing back..."
        "$APLAY_CMD" "$tmp_file" 2>/dev/null
        rm -f "$tmp_file"
        log_success "Microphone test complete."
    else
        log_error "Microphone test failed. No audio recorded."
        rm -f "$tmp_file"
        return 1
    fi
}

# --- ALSA Configuration Functions ---

show_alsa_config() {
    log_info "ALSA Configuration:"
    echo "==================================="
    
    if [ -f /proc/asound/cards ]; then
        echo "Sound Cards:"
        cat /proc/asound/cards
        echo ""
    fi
    
    if [ -f /proc/asound/modules ]; then
        echo "Modules:"
        cat /proc/asound/modules
        echo ""
    fi
    
    if [ -f /proc/asound/devices ]; then
        echo "Devices:"
        cat /proc/asound/devices
        echo ""
    fi
    
    if [ -f /proc/asound/pcm ]; then
        echo "PCM Devices:"
        cat /proc/asound/pcm
        echo ""
    fi
    
    # Show asound.conf if it exists
    if [ -f /etc/asound.conf ]; then
        echo "/etc/asound.conf:"
        cat /etc/asound.conf
        echo ""
    fi
    
    if [ -f ~/.asoundrc ]; then
        echo "~/.asoundrc:"
        cat ~/.asoundrc
        echo ""
    fi
    
    echo "==================================="
}

store_alsa_state() {
    log_info "Storing ALSA state..."
    
    if command -v alsactl > /dev/null 2>&1; then
        alsactl store 2>/dev/null
        log_success "ALSA state saved."
    else
        log_error "alsactl not found. Install 'alsa-utils'."
        return 1
    fi
}

restore_alsa_state() {
    log_info "Restoring ALSA state..."
    
    if command -v alsactl > /dev/null 2>&1; then
        alsactl restore 2>/dev/null
        log_success "ALSA state restored."
    else
        log_error "alsactl not found. Install 'alsa-utils'."
        return 1
    fi
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Sound Manager

Usage: $0 <command> [options]

Sound Card Detection:
  cards                       List all sound cards
  playback-devices            List playback (output) devices
  capture-devices             List capture (input/mic) devices
  default-devices             Show default audio devices

Audio Server Status:
  status                      Show audio server status (PipeWire/PulseAudio)
  restart                     Restart the audio server

Testing:
  test-speaker [device]      Play a test sound on speakers
  test-mic [duration]        Record and play back from microphone

ALSA Configuration:
  alsa-config                 Show ALSA configuration
  alsa-store                  Save current ALSA state
  alsa-restore                Restore saved ALSA state

Help:
  help                        Show this help message

Notes:
  - This utility complements 'audio_manager.sh' which handles volume control.
  - Audio server restart may cause brief audio interruption.
  - ALSA state is stored in /var/lib/alsa/asound.state.

Examples:
  $0 cards
  $0 status
  $0 test-speaker
  $0 test-mic 3
  $0 restart
HELP
}

# --- Main ---

main() {
    check_sound_deps
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        cards|list-cards)
            list_sound_cards
            ;;
        playback-devices|outputs)
            list_playback_devices
            ;;
        capture-devices|inputs)
            list_capture_devices
            ;;
        default-devices|defaults)
            show_default_devices
            ;;
        status|server-status)
            show_server_status
            ;;
        restart|restart-server)
            restart_audio_server
            ;;
        test-speaker|speaker-test)
            local device="${1:-}"
            test_speaker "$device"
            ;;
        test-mic|mic-test)
            local duration="${1:-3}"
            test_microphone "$duration"
            ;;
        alsa-config|alsa)
            show_alsa_config
            ;;
        alsa-store|store)
            store_alsa_state
            ;;
        alsa-restore|restore)
            restore_alsa_state
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