#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Devfs Setup
# Installs the custom /etc/default/devfs configuration for hardware access.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Device Filesystem (devfs)..."

    local devfs_src="/vice_payload/config/default/devfs"
    local devfs_dest="/etc/default/devfs"

    if [ ! -f "$devfs_src" ]; then
        log_error "devfs config file missing in payload: $devfs_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$devfs_src" "$devfs_dest"
    chown root:root "$devfs_dest"
    chmod 644 "$devfs_dest"
    log_info "Installed custom devfs configuration (Multimedia permissions)."

    log_success "Devfs setup completed."
}

main "$@"