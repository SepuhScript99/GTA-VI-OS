#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: APT Config Setup
# Installs global APT configurations to enforce the lightweight philosophy.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring APT global settings..."

    local apt_conf_src="/vice_payload/config/apt/apt.conf.d/99-no-recommends"
    local apt_conf_dest="/etc/apt/apt.conf.d/99-no-recommends"

    if [ ! -f "$apt_conf_src" ]; then
        log_error "APT config file missing in payload: $apt_conf_src! Aborting."
        exit 1
    fi

    # Ensure the destination directory exists
    mkdir -p /etc/apt/apt.conf.d

    cp "$apt_conf_src" "$apt_conf_dest"
    chown root:root "$apt_conf_dest"
    chmod 644 "$apt_conf_dest"
    log_info "Installed APT config to disable recommends/suggests."

    log_success "APT configuration completed."
}

main "$@"