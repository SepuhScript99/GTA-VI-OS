#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Networking Setup
# Installs the custom /etc/default/networking configuration.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring legacy networking daemon defaults..."

    local networking_src="/vice_payload/config/default/networking"
    local networking_dest="/etc/default/networking"

    if [ ! -f "$networking_src" ]; then
        log_error "Networking config file missing in payload: $networking_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$networking_src" "$networking_dest"
    chown root:root "$networking_dest"
    chmod 644 "$networking_dest"
    log_info "Installed custom networking configuration (Loopback enabled, no conflicts)."

    log_success "Networking setup completed."
}

main "$@"