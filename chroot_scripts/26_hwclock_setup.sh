#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: HWClock Setup
# Installs the custom /etc/default/hwclock configuration.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Hardware Clock (hwclock)..."

    local hwclock_src="/vice_payload/config/default/hwclock"
    local hwclock_dest="/etc/default/hwclock"

    if [ ! -f "$hwclock_src" ]; then
        log_error "hwclock config file missing in payload: $hwclock_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$hwclock_src" "$hwclock_dest"
    chown root:root "$hwclock_dest"
    chmod 644 "$hwclock_dest"
    log_info "Installed custom hwclock configuration (UTC)."

    log_success "HWClock setup completed."
}

main "$@"