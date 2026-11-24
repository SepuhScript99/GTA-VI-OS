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

    # Keep /etc/network/interfaces strictly loopback-only so NetworkManager owns all NICs
    mkdir -p /etc/network/interfaces.d
    find /etc/network/interfaces.d -maxdepth 1 -type f ! -name 'lo*' -delete 2>/dev/null || true
    cat <<'INTF' > /etc/network/interfaces
# This file describes the network interfaces available on your system
# and how to activate them. For more information, see interfaces(5).

source /etc/network/interfaces.d/*

# The loopback network interface
auto lo
iface lo inet loopback
INTF
    chown root:root /etc/network/interfaces
    chmod 644 /etc/network/interfaces

    log_success "Networking setup completed."
}

main "$@"
