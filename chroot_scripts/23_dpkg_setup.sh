#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: DPKG Setup
# Installs custom dpkg configurations for unattended upgrades.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring DPKG settings..."

    local dpkg_src="/vice_payload/config/dpkg/dpkg.cfg.d/force-confold"
    local dpkg_dest="/etc/dpkg/dpkg.cfg.d/force-confold"

    if [ ! -f "$dpkg_src" ]; then
        log_error "DPKG config file missing in payload: $dpkg_src! Aborting."
        exit 1
    fi

    # Ensure the destination directory exists
    mkdir -p /etc/dpkg/dpkg.cfg.d

    cp "$dpkg_src" "$dpkg_dest"
    chown root:root "$dpkg_dest"
    chmod 644 "$dpkg_dest"
    log_info "Installed DPKG configuration (force-confold)."

    log_success "DPKG setup completed."
}

main "$@"