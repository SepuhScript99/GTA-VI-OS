#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Avahi Setup
# Installs the custom /etc/default/avahi-daemon configuration.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Avahi daemon defaults..."

    local avahi_src="/vice_payload/config/default/avahi-daemon"
    local avahi_dest="/etc/default/avahi-daemon"

    if [ ! -f "$avahi_src" ]; then
        log_error "Avahi config file missing in payload: $avahi_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$avahi_src" "$avahi_dest"
    chown root:root "$avahi_dest"
    chmod 644 "$avahi_dest"
    log_info "Installed custom Avahi configuration (Local conflict detection enabled)."

    log_success "Avahi setup completed."
}

main "$@"