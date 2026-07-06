#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Smartmontools Setup
# Installs the custom /etc/default/smartmontools configuration for disk health.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Smartmontools daemon defaults..."

    local smartmontools_src="/vice_payload/config/default/smartmontools"
    local smartmontools_dest="/etc/default/smartmontools"

    if [ ! -f "$smartmontools_src" ]; then
        log_error "Smartmontools config file missing in payload: $smartmontools_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$smartmontools_src" "$smartmontools_dest"
    chown root:root "$smartmontools_dest"
    chmod 644 "$smartmontools_dest"
    log_info "Installed custom smartmontools configuration (1h interval, auto-enable)."

    log_success "Smartmontools setup completed."
}

main "$@"