#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Modprobe Setup
# Installs custom modprobe configurations (blacklists).
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Modprobe (Kernel Module) settings..."

    local modprobe_src="/vice_payload/config/modprobe.d/blacklist.conf"
    local modprobe_dest="/etc/modprobe.d/blacklist.conf"

    if [ ! -f "$modprobe_src" ]; then
        log_error "Modprobe config file missing in payload: $modprobe_src! Aborting."
        exit 1
    fi

    # Ensure the destination directory exists
    mkdir -p /etc/modprobe.d

    cp "$modprobe_src" "$modprobe_dest"
    chown root:root "$modprobe_dest"
    chmod 644 "$modprobe_dest"
    log_info "Installed module blacklist (blacklist.conf)."

    log_success "Modprobe setup completed."
}

main "$@"