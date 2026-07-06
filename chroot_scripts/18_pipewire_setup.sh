#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: PipeWire Setup
# Installs the custom PipeWire configuration for optimized audio.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring PipeWire audio server..."

    local pipewire_src="/vice_payload/config/pipewire/pipewire.conf"
    local pipewire_dest="/etc/pipewire/pipewire.conf"

    if [ ! -f "$pipewire_src" ]; then
        log_error "PipeWire config file missing in payload: $pipewire_src! Aborting."
        exit 1
    fi

    # Ensure the destination directory exists
    mkdir -p /etc/pipewire

    cp "$pipewire_src" "$pipewire_dest"
    chown root:root "$pipewire_dest"
    chmod 644 "$pipewire_dest"
    log_info "Installed custom PipeWire configuration (48000Hz, low-latency)."

    log_success "PipeWire setup completed."
}

main "$@"