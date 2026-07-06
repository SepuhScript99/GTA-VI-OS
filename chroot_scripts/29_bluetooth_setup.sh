#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Bluetooth Setup
# Installs the custom /etc/default/bluetooth configuration.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Bluetooth daemon..."

    local bluetooth_src="/vice_payload/config/default/bluetooth"
    local bluetooth_dest="/etc/default/bluetooth"

    if [ ! -f "$bluetooth_src" ]; then
        log_error "Bluetooth config file missing in payload: $bluetooth_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$bluetooth_src" "$bluetooth_dest"
    chown root:root "$bluetooth_dest"
    chmod 644 "$bluetooth_dest"
    log_info "Installed custom Bluetooth configuration (Experimental mode enabled)."

    log_success "Bluetooth setup completed."
}

main "$@"