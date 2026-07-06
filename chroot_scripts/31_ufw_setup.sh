#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: UFW Defaults Setup
# Installs the declarative /etc/default/ufw configuration.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring UFW Defaults (IPv6)..."

    local ufw_src="/vice_payload/config/default/ufw"
    local ufw_dest="/etc/default/ufw"

    if [ ! -f "$ufw_src" ]; then
        log_error "UFW config file missing in payload: $ufw_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$ufw_src" "$ufw_dest"
    chown root:root "$ufw_dest"
    chmod 644 "$ufw_dest"
    log_info "Installed declarative UFW defaults (IPv6 enabled)."

    log_success "UFW Defaults setup completed."
}

main "$@"