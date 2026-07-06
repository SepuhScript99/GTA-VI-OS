#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Saned Setup
# Installs the custom /etc/default/saned configuration for secure scanning.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring SANE daemon defaults..."

    local saned_src="/vice_payload/config/default/saned"
    local saned_dest="/etc/default/saned"

    if [ ! -f "$saned_src" ]; then
        log_error "Saned config file missing in payload: $saned_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$saned_src" "$saned_dest"
    chown root:root "$saned_dest"
    chmod 644 "$saned_dest"
    log_info "Installed custom saned configuration (Privilege drop enabled)."

    log_success "Saned setup completed."
}

main "$@"