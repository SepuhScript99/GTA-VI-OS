#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: NSSwitch Setup
# Installs the custom /etc/nsswitch.conf for optimized DNS/mDNS resolution.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Name Service Switch (nsswitch.conf)..."

    local nss_src="/vice_payload/config/default/nsswitch"
    local nss_dest="/etc/nsswitch.conf"

    if [ ! -f "$nss_src" ]; then
        log_error "nsswitch file missing in payload: $nss_src! Aborting."
        exit 1
    fi

    # Install to /etc/nsswitch.conf
    cp "$nss_src" "$nss_dest"
    chown root:root "$nss_dest"
    chmod 644 "$nss_dest"
    log_info "Installed custom nsswitch.conf (prioritizing files, mDNS, then DNS)."

    log_success "NSSwitch setup completed."
}

main "$@"