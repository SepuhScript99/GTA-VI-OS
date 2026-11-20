#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Ntpdate Setup
# Installs the custom /etc/default/ntpdate configuration to prevent conflicts.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring legacy ntpdate fallback..."

    local ntpdate_src="/vice_payload/config/default/ntpdate"
    local ntpdate_dest="/etc/default/ntpdate"

    if [ ! -f "$ntpdate_src" ]; then
        log_error "ntpdate config file missing in payload: $ntpdate_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$ntpdate_src" "$ntpdate_dest"
    chown root:root "$ntpdate_dest"
    chmod 644 "$ntpdate_dest"
    log_info "Installed legacy ntpdate configuration (Disabled to prevent conflicts)."

    log_success "Ntpdate setup completed."
}

main "$@"