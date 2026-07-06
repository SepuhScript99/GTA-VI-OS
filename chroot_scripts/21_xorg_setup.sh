#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Xorg Setup
# Installs custom Xorg configurations for input devices.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Xorg input settings..."

    local xorg_src="/vice_payload/config/X11/xorg.conf.d/10-input.conf"
    local xorg_dest="/etc/X11/xorg.conf.d/10-input.conf"

    if [ ! -f "$xorg_src" ]; then
        log_error "Xorg config file missing in payload: $xorg_src! Aborting."
        exit 1
    fi

    # Ensure the destination directory exists
    mkdir -p /etc/X11/xorg.conf.d

    cp "$xorg_src" "$xorg_dest"
    chown root:root "$xorg_dest"
    chmod 644 "$xorg_dest"
    log_info "Installed Xorg input configuration (10-input.conf)."

    log_success "Xorg setup completed."
}

main "$@"