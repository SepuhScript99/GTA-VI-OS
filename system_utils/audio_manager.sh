#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Audio Manager
# Provides volume control, mute toggling, and audio device management
# using pactl (PipeWire/PulseAudio compatibility layer).
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
PACTL_CMD="pactl"
DEFAULT_SINK="@DEFAULT_SINK@"
DEFAULT_SOURCE="@DEFAULT_SOURCE@"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Audio operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_audio_deps() {
    check_dependencies "pactl"
    
    # Check if audio server is running
    if ! $PACTL_CMD info > /dev/null 2>&1; then
        log_error "Cannot connect to PulseAudio/PipeWire server."
        log_info "Ensure the user is in the 'audio' group and the server is running."
        exit 1
    fi
}

# --- Volume Functions ---

get_volume() {
    local volume_str
    volume_str=$($PACTL_CMD get-sink-volume "$DEFAULT_SINK" 2>/dev/null | grep -o '[0-9]*%' | head -n 1)
    
    if [ -z "$volume_str" ]; then
        log_error "Could not retrieve volume. No default sink found."
        return 1
    fi
    
    # Strip the '%' and return just the number
    echo "${volume_str%\%}"
}

set_volume() {
    local level="$1"
    
    # Validate input is a number
    if ! [[ "$level" =~ ^[0-9]+$ ]]; then
        log_error "Volume must be a numeric value (0-150)."
        return 1
    fi
    
    # Allow up to 150% for boosting quiet audio
    if [ "$level" -lt 0 ] || [ "$level" -gt 150 ]; then
        log_error "Volume must be between 0 and 150."
        return 1
    fi
    
    log_info "Setting volume to ${level}%..."
    
    if ! $PACTL_CMD set-sink-volume "$DEFAULT_SINK" "${level}%"; then
        log_error "Failed to set volume."
        return 1
    fi
    
    log_success "Volume set to ${level}%."
}

change_volume() {
    local delta="$1"
    
    # Validate input format (e.g., +5 or -5)
    if ! [[ "$delta" =~ ^[+-][0-9]+$ ]]; then
        log_error "Volume change must be in the format +N or -N (e.g., +5, -10)."
        return 1
    fi
    
    local current new_level
    current=$(get_volume)
    
    # Calculate new level, clamped between 0 and 150
    new_level=$((current + delta))
    if [ "$new_level" -lt 0 ]; then
        new_level=0
    elif [ "$new_level" -gt 150 ]; then
        new_level=150
    fi
    
    set_volume "$new_level"
}

# --- Mute Functions ---

toggle_mute() {
    log_info "Toggling mute..."
    
    if ! $PACTL_CMD set-sink-mute "$DEFAULT_SINK" toggle; then
        log_error "Failed to toggle mute."
        return 1
    fi
    
    local mute_status
    mute_status=$($PACTL_CMD get-sink-mute "$DEFAULT_SINK" 2>/dev/null | awk '{print $2}')
    
    if [ "$mute_status" == "yes" ]; then
        log_success "Audio muted."
    else
        log_success "Audio unmuted."
    fi
}

mute() {
    log_info "Muting audio..."
    $PACTL_CMD set-sink-mute "$DEFAULT_SINK" 1 && log_success "Audio muted." || log_error "Failed to mute."
}

unmute() {
    log_info "Unmuting audio..."
    $PACTL_CMD set-sink-mute "$DEFAULT_SINK" 0 && log_success "Audio unmuted." || log_error "Failed to unmute."
}

# --- Device Management Functions ---

list_sinks() {
    log_info "Available Audio Outputs (Sinks):"
    echo "==================================="
    $PACTL_CMD list short sinks | awk '{printf "  ID: %s | Driver: %s | Description: %s\n", $1, $2, $NF}'
    echo "==================================="
}

list_sources() {
    log_info "Available Audio Inputs (Sources/Microphones):"
    echo "==================================="
    $PACTL_CMD list short sources | awk '{printf "  ID: %s | Driver: %s | Description: %s\n", $1, $2, $NF}'
    echo "==================================="
}

set_default_sink() {
    local sink_id="$1"
    
    log_info "Setting default sink to $sink_id..."
    
    if ! $PACTL_CMD set-default-sink "$sink_id"; then
        log_error "Failed to set default sink. Invalid ID?"
        return 1
    fi
    
    # Move existing streams to the new default sink
    $PACTL_CMD list short sink-inputs | awk '{print $1}' | while read -r input_id; do
        $PACTL_CMD move-sink-input "$input_id" "$sink_id" 2>/dev/null || true
    done
    
    log_success "Default sink set to $sink_id."
}

set_default_source() {
    local source_id="$1"
    
    log_info "Setting default source to $source_id..."
    
    if ! $PACTL_CMD set-default-source "$source_id"; then
        log_error "Failed to set default source. Invalid ID?"
        return 1
    fi
    
    # Move existing streams to the new default source
    $PACTL_CMD list short source-outputs | awk '{print $1}' | while read -r output_id; do
        $PACTL_CMD move-source-output "$output_id" "$source_id" 2>/dev/null || true
    done
    
    log_success "Default source set to $source_id."
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Audio Manager

Usage: $0 <command> [options]

Volume Control:
  get-volume                 Get current volume percentage
  set-volume <level>         Set volume (0-150)
  change-volume <+/-delta>   Increase/decrease volume (e.g., +5, -10)

Mute Control:
  toggle-mute                Toggle mute on/off
  mute                       Mute audio
  unmute                     Unmute audio

Device Management:
  list-sinks                 List available audio outputs
  list-sources               List available audio inputs (microphones)
  set-sink <id>              Set default audio output
  set-source <id>            Set default audio input

Help:
  help                       Show this help message

Examples:
  $0 get-volume
  $0 set-volume 50
  $0 change-volume +5
  $0 toggle-mute
  $0 list-sinks
  $0 set-sink 1
HELP
}

# --- Main ---

main() {
    check_audio_deps
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        get-volume)
            get_volume
            ;;
        set-volume)
            local level="${1:-}"
            if [ -z "$level" ]; then
                log_error "Volume level required."
                exit 1
            fi
            set_volume "$level"
            ;;
        change-volume|vol-up|vol-down)
            local delta="${1:-}"
            if [ -z "$delta" ]; then
                if [ "$command" == "vol-up" ]; then delta="+5"; fi
                if [ "$command" == "vol-down" ]; then delta="-5"; fi
            fi
            change_volume "$delta"
            ;;
        toggle-mute)
            toggle_mute
            ;;
        mute)
            mute
            ;;
        unmute)
            unmute
            ;;
        list-sinks)
            list_sinks
            ;;
        list-sources)
            list_sources
            ;;
        set-sink)
            local sink_id="${1:-}"
            if [ -z "$sink_id" ]; then
                log_error "Sink ID required."
                exit 1
            fi
            set_default_sink "$sink_id"
            ;;
        set-source)
            local source_id="${1:-}"
            if [ -z "$source_id" ]; then
                log_error "Source ID required."
                exit 1
            fi
            set_default_source "$source_id"
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